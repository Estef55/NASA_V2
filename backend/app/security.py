from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from fastapi import HTTPException
from .database import conn


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        calculated = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(calculated, expected)
    except (ValueError, TypeError):
        legacy = hashlib.pbkdf2_hmac('sha256', password.encode(), b'latira-demo-salt', 240000).hex()
        return hmac.compare_digest(legacy, encoded)


def auth(authorization: str | None):
    token = (authorization or '').removeprefix('Bearer ').strip()
    with conn() as connection:
        row = connection.execute(
            'SELECT u.* FROM sessions s JOIN users u ON u.username=s.username WHERE s.token=? AND s.expires>? AND u.active=1',
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    if not row:
        raise HTTPException(401, 'Sesión inválida o vencida')
    return dict(row)


def need(user, *roles):
    if user['role'] not in roles:
        raise HTTPException(403, 'Permiso insuficiente')
