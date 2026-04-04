"""
Autentifikacijos maršrutai.

Autorius: Paulius Turauskas
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Demo kredencialai (akademinis projektas)
_USERS: dict[str, str] = {
    "admin": "admin123",
}


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
    if stored is None or stored != body.password:
        raise HTTPException(status_code=401, detail="Neteisingas vartotojo vardas arba slaptažodis")
    token = hashlib.sha256(f"{body.username}:kursinis-demo".encode()).hexdigest()[:32]
    return LoginResponse(token=token, username=body.username)


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Atsijungimas (token ištrinamas kliento pusėje)."""
    return {"detail": "Sėkmingai atsijungta"}
