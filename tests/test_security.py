import hashlib

from dentalflow.security import verify_credentials


def test_verify_admin_password(monkeypatch):
    salt = b"0123456789abcdef"
    digest = hashlib.scrypt(b"clave-larga-y-segura", salt=salt, n=16384, r=8, p=1, dklen=32)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@clinica.test")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", f"scrypt$16384$8$1${salt.hex()}${digest.hex()}")
    assert verify_credentials("ADMIN@CLINICA.TEST", "clave-larga-y-segura")
    assert not verify_credentials("admin@clinica.test", "equivocada")
    assert not verify_credentials("otra@clinica.test", "clave-larga-y-segura")
