"""
Autentifikacijos maršrutai.

Demo lygio autentifikacija — slaptažodis kode (akademinis projektas).
Tokenas yra deterministinis hash, kurį patikrina kiti maršrutai per `verify_demo_token`.

Autorius: Paulius Turauskas
"""
from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Demo kredencialai (akademinis projektas — produkcijoje keisti į hash + DB)
_USERS: dict[str, str] = {
    "admin": "admin123",
}

_TOKEN_SALT = "kursinis-demo"


def _token_for(username: str) -> str:
    """Apskaičiuoja deterministinį demo tokeną pagal vartotojo vardą."""
    return hashlib.sha256(f"{username}:{_TOKEN_SALT}".encode()).hexdigest()[:32]


def verify_demo_token(token: str) -> bool:
    """
    Patikrina ar tokenas atitinka kurio nors žinomo vartotojo hash'ą.
    Naudoja constant-time palyginimą — apsaugo nuo timing atakų.
    """
    if not token:
        return False
    return any(hmac.compare_digest(token, _token_for(u)) for u in _USERS)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """Prisijungimas prie sistemos."""
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Vartotojo vardas ir slaptažodis privalomi")
    stored = _USERS.get(body.username)
    if stored is None or not hmac.compare_digest(stored, body.password):
        raise HTTPException(status_code=401, detail="Neteisingas vartotojo vardas arba slaptažodis")
    return LoginResponse(token=_token_for(body.username), username=body.username)


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Atsijungimas (token ištrinamas kliento pusėje)."""
    return {"detail": "Sėkmingai atsijungta"}
