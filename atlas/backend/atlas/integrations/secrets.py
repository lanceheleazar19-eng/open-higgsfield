"""Credenciales de integraciones. Se guardan en el Llavero del sistema (macOS Keychain /
Windows Credential Manager) mediante `keyring`. Si no hay llavero disponible, en
data/secrets.json con permisos 600 (solo el usuario). Nunca en la base de datos ni en git."""

import json
import os

import keyring
from keyring.errors import KeyringError

from atlas.config import get_settings

SERVICE = "atlas-personal-intelligence"


def _file():
    d = get_settings().resolved_data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "secrets.json"


def _keyring_ok() -> bool:
    kr = keyring.get_keyring()
    return getattr(kr, "priority", 0) > 0 and "fail" not in type(kr).__module__ and os.environ.get("ATLAS_NO_KEYRING") != "1"


def _read_file() -> dict:
    f = _file()
    return json.loads(f.read_text()) if f.exists() else {}


def _write_file(data: dict) -> None:
    f = _file()
    f.write_text(json.dumps(data))
    os.chmod(f, 0o600)


def set_secret(name: str, value: str) -> str:
    if _keyring_ok():
        try:
            keyring.set_password(SERVICE, name, value)
            return "keychain"
        except KeyringError:
            pass
    data = _read_file()
    data[name] = value
    _write_file(data)
    return "file"


def get_secret(name: str) -> str | None:
    if _keyring_ok():
        try:
            v = keyring.get_password(SERVICE, name)
            if v is not None:
                return v
        except KeyringError:
            pass
    return _read_file().get(name)


def delete_secret(name: str) -> None:
    if _keyring_ok():
        try:
            keyring.delete_password(SERVICE, name)
        except KeyringError:
            pass
    data = _read_file()
    if data.pop(name, None) is not None:
        _write_file(data)
