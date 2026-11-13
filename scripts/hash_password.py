"""Genera un hash scrypt; no almacena la contraseña en disco ni en GitHub."""
from getpass import getpass
import hashlib
import secrets

password = getpass("Contraseña de administrador (mín. 12 caracteres): ")
if len(password) < 12:
    raise SystemExit("Usa al menos 12 caracteres.")
salt = secrets.token_bytes(16)
digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
print("ADMIN_PASSWORD_HASH =", repr(f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"))
