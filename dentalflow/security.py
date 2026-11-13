"""Autenticación administrativa con scrypt (stdlib); secretos fuera del repositorio."""
from __future__ import annotations

import hashlib
import hmac
import os


def config(key: str, default: str = "") -> str:
    """Lee variables de entorno o secretos de Streamlit, sin filtrar excepciones."""
    value = os.getenv(key)
    if value is not None:
        return str(value)
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def is_demo() -> bool:
    return config("DEMO_MODE", "false").lower() == "true"


def verify_credentials(email: str, password: str) -> bool:
    expected_email = config("ADMIN_EMAIL").strip().lower()
    stored = config("ADMIN_PASSWORD_HASH").strip()
    if not expected_email or not stored or not email or not password:
        return False
    if not hmac.compare_digest(email.strip().lower(), expected_email):
        return False
    try:
        algorithm, n, r, p, salt, expected_hash = stored.split("$")
        if algorithm != "scrypt" or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                                n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(actual, bytes.fromhex(expected_hash))
    except (ValueError, TypeError, OverflowError):
        return False


def database_url() -> str:
    if is_demo():
        # Persistencia local exclusiva de demostración, no apta para datos reales.
        return "sqlite:///dentalflow_demo.sqlite3"
    return config("DATABASE_URL")
