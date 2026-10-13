"""
Vartotojų valdymo CLI.

  python -m app.manage_users list
  python -m app.manage_users add <vardas> --role admin|viewer [--password ...]
  python -m app.manage_users passwd <vardas> [--password ...]
  python -m app.manage_users delete <vardas>

Slaptažodis nenurodytas -> klausiama interaktyviai (getpass). Saugoma scrypt maiša
į USERS_DB_PATH (numatyta /state/users.json).
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.services.user_store import ROLES, UserStore


def _password(args) -> str:
    if args.password:
        return args.password
    pw = getpass.getpass("Slaptažodis: ")
    if pw != getpass.getpass("Pakartokite: "):
        sys.exit("Slaptažodžiai nesutampa")
    return pw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manage_users", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="users.json kelias (numatyta USERS_DB_PATH)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("add")
    p.add_argument("username")
    p.add_argument("--role", choices=ROLES, default="viewer")
    p.add_argument("--password")
    p = sub.add_parser("passwd")
    p.add_argument("username")
    p.add_argument("--password")
    p = sub.add_parser("delete")
    p.add_argument("username")
    args = parser.parse_args(argv)

    store = UserStore(args.db)
    if args.cmd == "list":
        for user, role in sorted(store.list_users().items()):
            print(f"{user}\t{role}")
    elif args.cmd == "add":
        store.set_user(args.username, _password(args), args.role)
        print(f"Pridėta: {args.username} ({args.role})")
    elif args.cmd == "passwd":
        users = store.list_users()
        if args.username not in users:
            sys.exit(f"Nėra vartotojo: {args.username}")
        store.set_user(args.username, _password(args), users[args.username])
        print(f"Slaptažodis pakeistas: {args.username}")
    elif args.cmd == "delete":
        if not store.delete_user(args.username):
            sys.exit(f"Nėra vartotojo: {args.username}")
        print(f"Pašalinta: {args.username}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
