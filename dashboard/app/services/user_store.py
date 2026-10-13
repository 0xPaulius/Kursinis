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


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
                        dklen=_DKLEN, maxmem=0)
    return dk.hex()


class UserStore:
    """Vartotojų CRUD su atominiu rašymu; slaptažodžiai niekada nesaugomi atviru tekstu."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("USERS_DB_PATH", "/state/users.json"))
        self._users: dict[str, dict] = self._load()
        if not self._users:
            self._bootstrap_admin()

    def _load(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._users, indent=2))
        os.replace(tmp, self.path)

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

    def verify(self, username: str, password: str) -> str | None:
        """Grąžina rolę, jei slaptažodis teisingas; kitaip None (constant-time)."""
        rec = self._users.get(username)
        if not rec:
            # Vykdome fiktyvų hash, kad atsako laikas neatskleistų ar vartotojas egzistuoja.
            _hash_password(password, b"0" * 16)
            return None
        candidate = _hash_password(password, bytes.fromhex(rec["salt"]))
        if hmac.compare_digest(candidate, rec["hash"]):
            return rec["role"]
        return None
