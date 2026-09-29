"""Explicit configuration; database credentials may stay in the environment."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess


def windows_persistent_acls(directory: Path) -> bool:
    """Query the actual mounted volume, including paths beneath mount points."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    api.GetVolumePathNameW.restype = wintypes.BOOL
    api.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD]
    api.GetVolumeInformationW.restype = wintypes.BOOL
    volume = ctypes.create_unicode_buffer(32768)
    if not api.GetVolumePathNameW(str(directory.resolve()), volume, len(volume)):
        raise ctypes.WinError(ctypes.get_last_error())
    flags = wintypes.DWORD()
    if not api.GetVolumeInformationW(volume.value, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(flags.value & 0x00000008)  # FILE_PERSISTENT_ACLS


def protect_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        if not windows_persistent_acls(directory):
            raise ValueError('AIR private storage requires persistent filesystem ACLs; FAT/exFAT are not supported')
        # Protect only AIR's own directory, never a parent or a shared workspace.
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                check=True, capture_output=True, text=True)
        import csv
        sid = next(csv.reader(result.stdout.strip().splitlines()))[1]
        subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r",
                        f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                       check=True, capture_output=True)
    else:
        directory.chmod(0o700)


def write_private(path: Path, value: dict) -> None:
    # Exclusive creation prevents accidental credential replacement and symlink writes.
    with path.open("x", encoding="utf-8") as stream:
        if os.name != "nt":
            os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")


@dataclass(frozen=True)
class Settings:
    home: Path
    database_url: str
    auth_mode: str = "local"
    oidc: dict = field(default_factory=dict)
    instance_id: str = "unconfigured"
    server: dict = field(default_factory=dict)

    @classmethod
    def load(cls, home: Path):
        home = home.resolve()
        data = json.loads((home / "config.json").read_text(encoding="utf-8"))
        if data.get("config_version") != 1:
            raise ValueError("Unsupported configuration version")
        mode = data.get("auth", {}).get("mode", "local")
        if mode not in ("local", "oidc"):
            raise ValueError("auth.mode must be local or oidc")
        url = os.environ.get("AIR_DATABASE_URL") or data.get("database_url")
        backend = data.get("database_backend")
        if backend not in (None, "sqlite", "postgresql"):
            raise ValueError("Unsupported declared database backend")
        if backend == "postgresql" and not url:
            raise ValueError("AIR_DATABASE_URL is required for this PostgreSQL installation")
        url = url or f"sqlite:///{(home / 'air.db').as_posix()}"
        if backend == "postgresql" and not url.startswith("postgresql+psycopg://") or backend == "sqlite" and not url.startswith("sqlite:///"):
            raise ValueError("Configured database backend differs; use an explicit registry transfer")
        if not url.startswith(("sqlite:///", "postgresql+psycopg://")):
            raise ValueError("Only SQLite and PostgreSQL/psycopg are supported")
        return cls(home, url, mode, data.get("auth", {}).get("oidc", {}), data["instance_id"], data.get("server", {}))
