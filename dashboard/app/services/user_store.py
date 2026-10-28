"""
Vartotojų saugykla su scrypt slaptažodžių maišomis (/state/users.json).

Pakeičia demonstracinį slaptažodį kode: slaptažodžiai saugomi tik kaip scrypt
maišos su atsitiktine druska. Rolės: `admin` (keičia įrenginius, atakas, pranešimus)
ir `viewer` (tik skaitymas). Pirmą kartą sukuriamas admin iš aplinkos kintamųjų
(DASHBOARD_ADMIN_USER / DASHBOARD_ADMIN_PASSWORD).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

ROLES = ("admin", "viewer")
# scrypt parametrai (OWASP rekomendacija: N=2**17); mažinami tik testams per env.
_SCRYPT_N = int(os.getenv("SCRYPT_N", str(2 ** 15)))
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32
# scrypt naudoja 128*N*r baitų; maxmem=0 reiškia OpenSSL ribą 32 MiB, o N=2**15
# jai reikia šiek tiek daugiau, todėl riba nurodoma aiškiai, su atsarga.
_SCRYPT_MAXMEM = 2 * 128 * _SCRYPT_N * _SCRYPT_R


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
                        dklen=_DKLEN, maxmem=_SCRYPT_MAXMEM)
    return dk.hex()


class UserStore:
    """Vartotojų CRUD su atominiu rašymu; slaptažodžiai niekada nesaugomi atviru tekstu."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("USERS_DB_PATH", "/state/users.json"))
        self._mtime: float | None = None
        self._users: dict[str, dict] = self._load()
        if not self._users:
            self._bootstrap_admin()

    def _load(self) -> dict[str, dict]:
        try:
            self._mtime = self.path.stat().st_mtime
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _refresh(self) -> None:
        """Perskaito failą, jei jį pakeitė kitas procesas (pvz. manage_users CLI)."""
        try:
            if self.path.stat().st_mtime != self._mtime:
                self._users = self._load()
        except FileNotFoundError:
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._users, indent=2))
        os.replace(tmp, self.path)
        self._mtime = self.path.stat().st_mtime

    def _bootstrap_admin(self) -> None:
        user = os.getenv("DASHBOARD_ADMIN_USER", "admin")
        password = os.getenv("DASHBOARD_ADMIN_PASSWORD", "admin123")
        if password == "admin123":
            logger.warning("DASHBOARD_ADMIN_PASSWORD nenustatytas — naudojamas demonstracinis "
                           "slaptažodis. Produkcijoje nustatykite stiprų slaptažodį.")
        self.set_user(user, password, "admin")

    # -- CRUD -----------------------------------------------------------------

    def set_user(self, username: str, password: str, role: str = "viewer") -> None:
        if role not in ROLES:
            raise ValueError(f"Neteisinga rolė: {role} (galimos: {', '.join(ROLES)})")
        if not username or not password:
            raise ValueError("Vartotojo vardas ir slaptažodis privalomi")
        salt = secrets.token_bytes(16)
        self._users[username] = {"role": role, "salt": salt.hex(),
                                 "hash": _hash_password(password, salt)}
        self._save()

    def delete_user(self, username: str) -> bool:
        if username in self._users:
            del self._users[username]
            self._save()
            return True
        return False

    def list_users(self) -> dict[str, str]:
        """{vartotojo vardas: rolė} — be maišų."""
        return {u: rec["role"] for u, rec in self._users.items()}

    def role(self, username: str) -> str | None:
        """Dabartinė vartotojo rolė arba None, jei vartotojo nebėra (įskaitant CLI pakeitimus)."""
        self._refresh()
        rec = self._users.get(username)
        return rec["role"] if rec else None

    def verify(self, username: str, password: str) -> str | None:
        """Grąžina rolę, jei slaptažodis teisingas; kitaip None (constant-time)."""
        self._refresh()
        rec = self._users.get(username)
        if not rec:
            # Vykdome fiktyvų hash, kad atsako laikas neatskleistų ar vartotojas egzistuoja.
            _hash_password(password, b"0" * 16)
            return None
        candidate = _hash_password(password, bytes.fromhex(rec["salt"]))
        if hmac.compare_digest(candidate, rec["hash"]):
            return rec["role"]
        return None
