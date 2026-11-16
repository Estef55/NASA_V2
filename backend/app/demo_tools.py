"""Secure local CLI and helper utility to prepare, inspect, and reset LÁTIRA 2.0 demo accounts and scenario.

Safety guarantees:
- Refuses to create, enable, or disclose demo accounts when LATIRA_ENV != 'demo' or LATIRA_DEMO_LOGIN=false.
- Generates unique cryptographically random high-entropy passwords per demo account (never weak fixed passwords).
- Never overwrites existing users or modifies real accounts/data (demo=0).
- Clears demo followups before demo alerts/metrics to preserve SQLite foreign-key integrity.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import database


def _get_app_main():
    mod_name = f"{__package__}.main" if __package__ else "app.main"
    existing = sys.modules.get(mod_name)
    if existing is not None:
        return existing
    old_env = os.environ.get("LATIRA_ENV")
    old_pwd = os.environ.get("LATIRA_DEMO_PASSWORD")
    try:
        os.environ["LATIRA_ENV"] = "production"
        os.environ.pop("LATIRA_DEMO_PASSWORD", None)
        from . import main as app_main
        return app_main
    finally:
        if old_env is None:
            os.environ.pop("LATIRA_ENV", None)
        else:
            os.environ["LATIRA_ENV"] = old_env
        if old_pwd is not None:
            os.environ["LATIRA_DEMO_PASSWORD"] = old_pwd


def _init_schema_without_demo_autoseed():
    app_main = _get_app_main()
    old_env = os.environ.get("LATIRA_ENV")
    old_pwd = os.environ.get("LATIRA_DEMO_PASSWORD")
    try:
        os.environ["LATIRA_ENV"] = "production"
        os.environ.pop("LATIRA_DEMO_PASSWORD", None)
        app_main.init()
    finally:
        if old_env is None:
            os.environ.pop("LATIRA_ENV", None)
        else:
            os.environ["LATIRA_ENV"] = old_env
        if old_pwd is not None:
            os.environ["LATIRA_DEMO_PASSWORD"] = old_pwd
    return app_main


_ALPHABET_UPPER = string.ascii_uppercase
_ALPHABET_LOWER = string.ascii_lowercase
_ALPHABET_DIGITS = string.digits
_ALPHABET_SYM = "!@#$%^&*-_=+"
_ALPHABET_ALL = _ALPHABET_UPPER + _ALPHABET_LOWER + _ALPHABET_DIGITS + _ALPHABET_SYM


class DemoToolError(RuntimeError):
    """Raised when a demo utility operation is blocked by environment or validation policy."""


def generate_strong_password(length: int = 24) -> str:
    """Generate a cryptographically random password with guaranteed character diversity."""
    if length < 16:
        raise ValueError("Demo password length must be at least 16 characters")
    chars = [
        secrets.choice(_ALPHABET_UPPER),
        secrets.choice(_ALPHABET_LOWER),
        secrets.choice(_ALPHABET_DIGITS),
        secrets.choice(_ALPHABET_SYM),
    ]
    chars.extend(secrets.choice(_ALPHABET_ALL) for _ in range(length - len(chars)))
    # Fisher-Yates shuffle using secrets.randbelow
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def get_credentials_file_path() -> Path:
    override = (os.getenv("LATIRA_DEMO_CREDENTIALS_FILE") or "").strip()
    if override:
        return Path(override)
    return database.DB.parent / ".demo_credentials.json"


def _require_demo_environment() -> None:
    env = (os.getenv("LATIRA_ENV") or "production").strip().lower()
    flag = (os.getenv("LATIRA_DEMO_LOGIN") or "").strip().lower()
    if env != "demo":
        raise DemoToolError(
            "Operación bloqueada: las utilidades de demostración solo funcionan cuando LATIRA_ENV=demo "
            f"(entorno actual: '{env or 'production'}'). En producción las cuentas demo permanecen deshabilitadas."
        )
    if flag in ("0", "false", "no", "off"):
        raise DemoToolError(
            "Operación bloqueada: LATIRA_DEMO_LOGIN está deshabilitado explícitamente."
        )


def _load_credentials_store(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"accounts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("accounts"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"accounts": {}}


def _save_credentials_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def prepare_demo_environment(*, scenario_days: int = 0) -> dict[str, Any]:
    """Create missing demo accounts with random strong passwords without overwriting existing users."""
    _require_demo_environment()
    if scenario_days < 0 or scenario_days > 5:
        raise DemoToolError("scenario_days debe estar entre 0 y 5")

    # Initialize schema without auto-seeding random untracked demo passwords first,
    # or handle existing accounts cleanly without overwriting them.
    # Temporarily inspect which demo usernames exist BEFORE init() runs ensure_demo_accounts.
    database.DB.parent.mkdir(parents=True, exist_ok=True)
    pre_existing: set[str] = set()
    with database.conn() as c:
        has_users = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if has_users:
            rows = c.execute("SELECT username FROM users").fetchall()
            pre_existing = {r["username"] for r in rows}

    # Ensure schema exists without letting init() insert demo accounts with untracked secrets.
    app_main = _init_schema_without_demo_autoseed()

    cred_path = get_credentials_file_path()
    store = _load_credentials_store(cred_path)
    accounts_store: dict[str, Any] = store.setdefault("accounts", {})

    created: list[str] = []
    preserved_existing: list[str] = []

    with database.conn() as c:
        for spec in app_main.DEMO_PROFILE_SPECS:
            uname = spec["username"]
            row = c.execute(
                "SELECT username, role, astronaut_id, active FROM users WHERE username=?",
                (uname,),
            ).fetchone()
            if row:
                preserved_existing.append(uname)
                if uname not in accounts_store:
                    accounts_store[uname] = {
                        "profile": spec["profile"],
                        "username": uname,
                        "role": row["role"],
                        "astronaut_id": row["astronaut_id"],
                        "password": None,
                        "status": "existing_preserved",
                    }
                continue

            pwd = generate_strong_password(24)
            c.execute(
                "INSERT INTO users(username,password_hash,role,astronaut_id,active) VALUES(?,?,?,?,1)",
                (uname, app_main.hash_password(pwd), spec["role"], spec["astronaut_id"]),
            )
            created.append(uname)
            accounts_store[uname] = {
                "profile": spec["profile"],
                "username": uname,
                "role": spec["role"],
                "astronaut_id": spec["astronaut_id"],
                "password": pwd,
                "status": "generated",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        c.execute(
            "INSERT OR IGNORE INTO assignments(medic_username,astronaut_id) "
            "SELECT 'medic_demo','AST-001' "
            "WHERE EXISTS(SELECT 1 FROM users WHERE username='medic_demo' AND role='medic') "
            "AND EXISTS(SELECT 1 FROM users WHERE astronaut_id='AST-001' AND role='astronaut')"
        )

        app_main._clear_demo_scenario(c, "AST-001")
        if scenario_days > 0:
            app_main._set_owner_demo_state(c, "AST-001", scenario_days, 1)
            for d in range(1, scenario_days + 1):
                app_main.add_demo_day(c, d, "AST-001")
        else:
            app_main._set_owner_demo_state(c, "AST-001", 0, 0)

    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    store["environment"] = "demo"
    _save_credentials_store(cred_path, store)

    return {
        "ok": True,
        "environment": "demo",
        "created_accounts": created,
        "preserved_existing_accounts": preserved_existing,
        "pre_existing_users_count": len(pre_existing),
        "scenario_days": scenario_days,
        "credentials_file": cred_path.name,
    }


def get_demo_credentials() -> dict[str, Any]:
    """Read locally generated demo credentials only when LATIRA_ENV=demo."""
    _require_demo_environment()
    cred_path = get_credentials_file_path()
    store = _load_credentials_store(cred_path)
    accounts = store.get("accounts", {})

    app_main = _get_app_main()
    entries: list[dict[str, Any]] = []
    with database.conn() as c:
        has_users = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        for spec in app_main.DEMO_PROFILE_SPECS:
            uname = spec["username"]
            db_row = (
                c.execute(
                    "SELECT username, role, astronaut_id, active FROM users WHERE username=?",
                    (uname,),
                ).fetchone()
                if has_users
                else None
            )
            saved = accounts.get(uname) or {}
            entries.append(
                {
                    "profile": spec["profile"],
                    "username": uname,
                    "role": db_row["role"] if db_row else spec["role"],
                    "astronaut_id": db_row["astronaut_id"] if db_row else spec["astronaut_id"],
                    "active": bool(db_row["active"]) if db_row else False,
                    "exists_in_db": bool(db_row),
                    "password": saved.get("password"),
                    "password_status": (
                        "available_locally"
                        if saved.get("password")
                        else ("existing_preserved_not_overwritten" if db_row else "not_prepared")
                    ),
                }
            )
    return {
        "ok": True,
        "environment": "demo",
        "credentials_file_present": cred_path.is_file(),
        "accounts": entries,
    }


def reset_demo_environment(*, all_astronauts: bool = False) -> dict[str, Any]:
    """Reset demo scenario (demo=1) safely without deleting real records (demo=0) or users."""
    _require_demo_environment()
    app_main = _init_schema_without_demo_autoseed()
    with database.conn() as c:
        if all_astronauts:
            aids = [
                r["astronaut_id"]
                for r in c.execute(
                    "SELECT DISTINCT astronaut_id FROM ("
                    "SELECT astronaut_id FROM metrics WHERE demo=1 "
                    "UNION SELECT astronaut_id FROM alerts WHERE demo=1 "
                    "UNION SELECT astronaut_id FROM checkins WHERE demo=1 "
                    "UNION SELECT astronaut_id FROM demo_owner_state"
                    ")"
                ).fetchall()
                if r["astronaut_id"]
            ]
            if "AST-001" not in aids:
                aids.append("AST-001")
        else:
            aids = ["AST-001"]

        for aid in aids:
            app_main._clear_demo_scenario(c, aid)
            app_main._set_owner_demo_state(c, aid, 0, 0)

    return {
        "ok": True,
        "environment": "demo",
        "reset_astronauts": sorted(aids),
        "real_data_preserved": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo_tools",
        description="Utilidad local segura para preparar, consultar y restablecer el escenario demo de LÁTIRA 2.0.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="Prepara cuentas demo faltantes (con claves aleatorias) y escenario reproducible.")
    p_prep.add_argument("--days", type=int, default=0, help="Días iniciales de escenario demo a sembrar (0 a 5, predeterminado 0).")
    p_prep.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    p_show = sub.add_parser("show", help="Consulta localmente las credenciales demo generadas (solo en LATIRA_ENV=demo).")
    p_show.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    p_reset = sub.add_parser("reset", help="Restablece datos de demostración (demo=1) sin borrar datos reales (demo=0) ni usuarios.")
    p_reset.add_argument("--all", action="store_true", help="Restablece el estado demo para todos los IDs de astronauta con datos demo.")
    p_reset.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    args = parser.parse_args(argv)

    try:
        if args.command == "prepare":
            res = prepare_demo_environment(scenario_days=args.days)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[OK] Entorno demo preparado (escenario={res['scenario_days']} días).")
                print(f"     Cuentas creadas: {', '.join(res['created_accounts']) or 'ninguna (ya existían)'}")
                print(f"     Cuentas existentes preservadas: {', '.join(res['preserved_existing_accounts']) or 'ninguna'}")
                print("     Consulta local: python -m app.demo_tools show")
            return 0

        if args.command == "show":
            res = get_demo_credentials()
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print("Credenciales locales de demostración (LATIRA_ENV=demo):")
                for acc in res["accounts"]:
                    pwd_display = acc["password"] or f"[{acc['password_status']}]"
                    print(
                        f"  - perfil={acc['profile']} usuario={acc['username']} "
                        f"rol={acc['role']} astronaut_id={acc['astronaut_id'] or '-'} "
                        f"password={pwd_display}"
                    )
            return 0

        if args.command == "reset":
            res = reset_demo_environment(all_astronauts=bool(args.all))
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"[OK] Escenario demo restablecido para: {', '.join(res['reset_astronauts'])} (datos reales intactos).")
            return 0
    except DemoToolError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
