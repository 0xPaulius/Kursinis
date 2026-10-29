"""
Autentifikacijos maršrutai.

Vartotojai saugomi scrypt maišomis (UserStore, /state/users.json). Prisijungus
išduodamas HMAC parašu pasirašytas tokenas su galiojimo laiku ir role; kiti
maršrutai jį tikrina per `verify_token` (dependencies.py). Nesėkmingi bandymai
ribojami (login throttling).

Autorius: Paulius Turauskas
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.user_store import UserStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

TOKEN_TTL_SECONDS = int(os.getenv("DASHBOARD_TOKEN_TTL", "28800"))  # 8 val.
_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "300"))

_store: UserStore | None = None
# Nesėkmingi bandymai: kliento IP -> (skaičius, pirmo bandymo laikas). Raktas — tik IP:
# kitaip keičiant vartotojo vardą riba nesuveiktų, o kiekvienas bandymas vykdo lėtą scrypt.
_failures: dict[str, tuple[int, float]] = {}


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        _store = UserStore()
    return _store


def _secret() -> bytes:
    """Tokenų parašo raktas: iš DASHBOARD_SECRET_KEY arba sugeneruotas į /state/secret.key."""
    env = os.getenv("DASHBOARD_SECRET_KEY")
    if env:
        return env.encode()
    path = Path(os.getenv("SECRET_KEY_PATH", "/state/secret.key"))
    if path.exists():
        return path.read_bytes()
    key = secrets.token_bytes(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(key)
        os.chmod(path, 0o600)
    except OSError as exc:  # pragma: no cover
        logger.warning("Nepavyko išsaugoti tokenų rakto (%s) — naudojamas laikinas", exc)
    return key


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(username: str, role: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    """Pasirašytas tokenas: base64(payload).base64(hmac-sha256)."""
    payload = _b64(json.dumps({"u": username, "r": role, "exp": int(time.time()) + ttl}).encode())
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{_b64(sig)}"


def verify_token(token: str) -> dict | None:
    """Patikrina parašą ir galiojimą. Grąžina {"u","r","exp"} arba None."""
    if not token or token.count(".") != 1:
        return None
    payload, sig = token.split(".")
    expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(_unb64(sig), expected):
            return None
        claims = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict) or claims.get("exp", 0) < time.time():
        return None
    return claims


def verify_session(token: str) -> dict | None:
    """verify_token + vartotojas vis dar egzistuoja ir turi tą pačią rolę (ištrintas ar
    pažemintas vartotojas su dar galiojančiu tokenu atmetamas)."""
    claims = verify_token(token)
    if claims is None or get_user_store().role(str(claims.get("u", ""))) != claims.get("r"):
        return None
    return claims


def _check_throttle(key: str) -> None:
    record = _failures.get(key)
    if record and record[0] >= _MAX_FAILURES and time.time() - record[1] < _LOCKOUT_SECONDS:
        retry = int(_LOCKOUT_SECONDS - (time.time() - record[1]))
        raise HTTPException(status_code=429, detail=f"Per daug bandymų. Bandykite po {retry} s.",
                            headers={"Retry-After": str(retry)})


def _record_failure(key: str) -> None:
    count, first = _failures.get(key, (0, time.time()))
    if time.time() - first >= _LOCKOUT_SECONDS:
        count, first = 0, time.time()
    _failures[key] = (count + 1, first)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    expires_in: int


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """Prisijungimas: tikrina kredencialus, riboja nesėkmingus bandymus, išduoda tokeną."""
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Vartotojo vardas ir slaptažodis privalomi")

    key = request.client.host if request.client else "?"
    _check_throttle(key)

    role = get_user_store().verify(body.username, body.password)
    if role is None:
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Neteisingas vartotojo vardas arba slaptažodis")

    _failures.pop(key, None)
    return LoginResponse(token=issue_token(body.username, role), username=body.username,
                         role=role, expires_in=TOKEN_TTL_SECONDS)


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Atsijungimas (tokenas ištrinamas kliento pusėje; serveris jų nesaugo)."""
    return {"detail": "Sėkmingai atsijungta"}
