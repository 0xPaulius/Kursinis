"""
Autentifikacijos testai: UserStore (scrypt), tokenai, rolės, throttling ir CLI.
"""
from __future__ import annotations

import importlib
import time

import pytest
from fastapi import HTTPException

from app.services.user_store import UserStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRYPT_N", "1024")
    return UserStore(tmp_path / "users.json")


@pytest.fixture
def auth(tmp_path, monkeypatch):
    """Šviežiai perkrautas auth modulis su izoliuotu raktu ir vartotojų baze."""
    monkeypatch.setenv("SCRYPT_N", "1024")
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("USERS_DB_PATH", str(tmp_path / "users.json"))
    import app.routers.auth as auth_module
    importlib.reload(auth_module)
    auth_module._failures.clear()
    return auth_module


# -- UserStore ---------------------------------------------------------------

def test_passwords_hashed_not_plaintext(store, tmp_path):
    store.set_user("alice", "s3cret", "admin")
    raw = (tmp_path / "users.json").read_text()
    assert "s3cret" not in raw
    assert store._users["alice"]["hash"] != "s3cret"
    assert len(store._users["alice"]["salt"]) == 32  # 16 baitų hex


def test_verify_correct_and_wrong_password(store):
    store.set_user("bob", "right", "viewer")
    assert store.verify("bob", "right") == "viewer"
    assert store.verify("bob", "wrong") is None
    assert store.verify("ghost", "x") is None


def test_salt_is_random_per_user(store):
    store.set_user("a", "same-password", "viewer")
    store.set_user("b", "same-password", "viewer")
    assert store._users["a"]["hash"] != store._users["b"]["hash"]


def test_bootstrap_admin_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRYPT_N", "1024")
    monkeypatch.setenv("DASHBOARD_ADMIN_USER", "root")
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD", "bootstrap-pw")
    store = UserStore(tmp_path / "users.json")
    assert store.list_users() == {"root": "admin"}
    assert store.verify("root", "bootstrap-pw") == "admin"


def test_persistence_across_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRYPT_N", "1024")
    path = tmp_path / "users.json"
    UserStore(path).set_user("carol", "pw", "viewer")
    assert UserStore(path).verify("carol", "pw") == "viewer"


def test_invalid_role_rejected(store):
    with pytest.raises(ValueError):
        store.set_user("x", "pw", "superuser")


# -- Tokens ------------------------------------------------------------------

def test_token_roundtrip_carries_role(auth):
    claims = auth.verify_token(auth.issue_token("alice", "admin"))
    assert claims["u"] == "alice" and claims["r"] == "admin"


def test_expired_token_rejected(auth):
    assert auth.verify_token(auth.issue_token("alice", "admin", ttl=-1)) is None


def test_tampered_token_rejected(auth):
    token = auth.issue_token("alice", "viewer")
    payload, sig = token.split(".")
    # Pakeista rolė payload'e be naujo parašo -> atmetama.
    import base64, json
    forged = json.loads(base64.urlsafe_b64decode(payload + "=="))
    forged["r"] = "admin"
    bad_payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()
    assert auth.verify_token(f"{bad_payload}.{sig}") is None


def test_token_signed_with_other_key_rejected(auth, monkeypatch):
    token = auth.issue_token("alice", "admin")
    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "different-key")
    importlib.reload(auth)
    assert auth.verify_token(token) is None


def test_garbage_tokens_rejected(auth):
    for junk in ["", "no-dot", "a.b.c", "....", "x." + "y" * 10]:
        assert auth.verify_token(junk) is None


# -- Throttling --------------------------------------------------------------

def test_throttle_locks_after_max_failures(auth, monkeypatch):
    monkeypatch.setattr(auth, "_MAX_FAILURES", 3)
    monkeypatch.setattr(auth, "_LOCKOUT_SECONDS", 300)
    key = "user|1.2.3.4"
    for _ in range(3):
        auth._record_failure(key)
    with pytest.raises(HTTPException) as exc:
        auth._check_throttle(key)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_throttle_window_resets(auth, monkeypatch):
    monkeypatch.setattr(auth, "_MAX_FAILURES", 3)
    monkeypatch.setattr(auth, "_LOCKOUT_SECONDS", 0)  # langas iškart pasibaigęs
    key = "user|1.2.3.4"
    for _ in range(5):
        auth._record_failure(key)
    auth._check_throttle(key)  # neturi mesti — langas pasibaigęs


# -- CLI ---------------------------------------------------------------------

def test_cli_add_list_delete(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCRYPT_N", "1024")
    from app import manage_users
    db = str(tmp_path / "users.json")
    manage_users.main(["--db", db, "add", "dave", "--role", "admin", "--password", "pw"])
    manage_users.main(["--db", db, "list"])
    assert "dave\tadmin" in capsys.readouterr().out
    assert UserStore(db).verify("dave", "pw") == "admin"
    manage_users.main(["--db", db, "delete", "dave"])
    assert "dave" not in UserStore(db).list_users()
