"""
KSP CrimeIQ — Authentication Module
JWT tokens + direct bcrypt.
Users are persisted in the same SQLite database used by all other modules.
Pre-seeded accounts are written to the DB on first startup (INSERT OR IGNORE).
"""

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import logging

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

logger = logging.getLogger("ksp_crimeiq.auth")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
_secret = os.getenv("KSP_SECRET")
if not _secret:
    raise RuntimeError(
        "KSP_SECRET environment variable is not set. "
        "Copy .env and set a strong random value before starting the server. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
SECRET_KEY          = _secret
ALGORITHM           = "HS256"
TOKEN_EXPIRE_HOURS  = 8

DB_PATH = "data/crime_db.sqlite"

bearer = HTTPBearer(auto_error=False)

# ─────────────────────────────────────────────────────────────
# PASSWORD UTILS  (direct bcrypt — no passlib)
# ─────────────────────────────────────────────────────────────
def _hash(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=10))

def _verify(plain: str, hashed: bytes | str) -> bool:
    try:
        if isinstance(hashed, str):
            hashed = hashed.encode("utf-8")
        return bcrypt.checkpw(plain.encode("utf-8"), hashed)
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────
from db import get_db
_get_db = get_db

def _ensure_users_table() -> None:
    """Create the users table if it does not exist yet."""
    conn = _get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username     TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'investigator',
                display_name TEXT NOT NULL DEFAULT '',
                role_label   TEXT NOT NULL DEFAULT 'Officer',
                badge        TEXT NOT NULL DEFAULT '',
                avatar_color TEXT NOT NULL DEFAULT '#10b981'
            )
        """)
        conn.commit()
    finally:
        conn.close()

def _row_to_user(row: sqlite3.Row) -> dict:
    """Convert a DB row to the user dict consumed by FastAPI dependencies."""
    return {
        "username":      row["username"],
        "password_hash": row["password_hash"],   # stored as text in SQLite
        "role":          row["role"],
        "display_name":  row["display_name"],
        "role_label":    row["role_label"],
        "badge":         row["badge"],
        "avatar_color":  row["avatar_color"],
    }

DEMO_PASSWORDS = {
    "admin":        os.getenv("ADMIN_PASSWORD", secrets.token_urlsafe(9)),
    "investigator": os.getenv("INVESTIGATOR_PASSWORD", secrets.token_urlsafe(9)),
    "analyst":      os.getenv("ANALYST_PASSWORD", secrets.token_urlsafe(9)),
    "sho":          os.getenv("SHO_PASSWORD", secrets.token_urlsafe(9)),
}

def _seed_default_users() -> None:
    """Insert or update the four demo accounts with secure passwords."""
    _RAW = {
        "admin":        (DEMO_PASSWORDS["admin"],        "commander",   "DCP Vikram Sharma",     "District Commander",    "KSP/DC/001",  "#3b82f6"),
        "investigator": (DEMO_PASSWORDS["investigator"], "investigator","SI Priya Nair",         "Investigator",          "KSP/SI/042",  "#8b5cf6"),
        "analyst":      (DEMO_PASSWORDS["analyst"],      "analyst",     "Ravi Kumar (SCRB)",     "SCRB Analyst",          "KSP/AN/007",  "#06b6d4"),
        "sho":          (DEMO_PASSWORDS["sho"],          "sho",         "Inspector Meera Gowda", "Station House Officer", "KSP/SHO/019", "#10b981"),
    }
    role_labels = {
        "commander":   "District Commander",
        "investigator":"Investigator",
        "analyst":     "SCRB Analyst",
        "sho":         "Station House Officer",
    }
    conn = _get_db()
    try:
        for uname, raw in _RAW.items():
            pwd, role, display_name, role_label, badge, avatar_color = raw
            pwd_hash = _hash(pwd).decode("utf-8")
            existing = conn.execute("SELECT username FROM users WHERE username = ?", (uname,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (pwd_hash, uname)
                )
            else:
                conn.execute(
                    """INSERT INTO users
                       (username, password_hash, role, display_name, role_label, badge, avatar_color)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (uname, pwd_hash, role, display_name,
                     role_labels.get(role, "Officer"), badge, avatar_color),
                )
        conn.commit()
    finally:
        conn.close()

    logger.info("KSP CrimeIQ Active Demo Credentials:")
    for u, p in DEMO_PASSWORDS.items():
        logger.info(f"  {u.capitalize():<15} username: {u:<14} password: {p}")


# Run table creation + seeding at import time
_ensure_users_table()
_seed_default_users()


# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    username: str
    password: str
    display_name: str
    role: str
    badge: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

# ─────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────
def authenticate_user(username: str, password: str) -> Optional[dict]:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.lower().strip(),)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if not _verify(password, row["password_hash"]):
        return None
    return _row_to_user(row)

def register_user(req: SignupRequest) -> dict:
    uname = req.username.lower().strip()
    role_labels = {
        "commander":   "District Commander",
        "investigator":"Investigator",
        "analyst":     "SCRB Analyst",
        "sho":         "Station House Officer",
    }
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT username FROM users WHERE username = ?", (uname,)
        ).fetchone()
        if existing:
            raise ValueError("Username already exists")
        pwd_hash = _hash(req.password).decode("utf-8")
        role = req.role.lower()
        conn.execute(
            """INSERT INTO users (username, password_hash, role, display_name, role_label, badge, avatar_color)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uname, pwd_hash, role, req.display_name,
             role_labels.get(role, "Officer"), req.badge, "#10b981"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (uname,)).fetchone()
        return _row_to_user(row)
    finally:
        conn.close()

def create_access_token(data: dict) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def _get_user_by_name(username: str) -> Optional[dict]:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────
# FASTAPI DEPENDENCY
# ─────────────────────────────────────────────────────────────
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        user = _get_user_by_name(username)
        if not user:
            raise ValueError("user not found")
        return user
    except (JWTError, ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_roles(allowed_roles: list[str]):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )
        return current_user
    return role_checker

# ─────────────────────────────────────────────────────────────
# BACKWARD-COMPAT SHIM — main.py imports USERS_DB; keep it
# working as a passthrough so no routes break.
# This dict is NOT used for lookups anymore — all reads go to DB.
# ─────────────────────────────────────────────────────────────
class _UsersDBShim:
    """Thin shim so `USERS_DB.get(x)` still works in main.py without changes."""
    def get(self, key, default=None):
        return _get_user_by_name(key) or default

    def __contains__(self, key):
        return _get_user_by_name(key) is not None

USERS_DB = _UsersDBShim()
