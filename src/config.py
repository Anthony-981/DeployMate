from __future__ import annotations

import os
import sys
import hashlib
from pathlib import Path

APP_NAME = "DeployMate"
APP_VERSION = "V1.1"


def _release_build_id() -> str:
    if not getattr(sys, "frozen", False):
        return "dev"
    try:
        digest = hashlib.sha256()
        with open(sys.executable, "rb") as stream:
            digest.update(stream.read(1024 * 1024))
        return digest.hexdigest()[:12]
    except OSError:
        return "unknown"


def get_db_mode() -> str:
    # Packaged releases must never inherit a development-mode environment value.
    if getattr(sys, "frozen", False):
        return "prod"
    configured = os.getenv("DEPLOYMATE_DB_MODE")
    if configured:
        return configured.strip().lower()
    return "dev"


def resolve_db_path(db_path: str | None = None, db_mode: str | None = None) -> str:
    if db_path:
        return str(Path(db_path))

    # A privately shared package keeps its database beside the executable so
    # the recipient can unzip and launch it without an import/restore step.
    portable_db = resolve_portable_db_path()
    if portable_db is not None:
        return str(portable_db)

    mode = (db_mode or get_db_mode() or "dev").strip().lower()
    data_dir = resolve_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    file_name = "deploymate.db" if mode == "prod" else "deploymate_dev.db"
    return str(data_dir / file_name)


def resolve_portable_db_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys.executable).resolve().parent / "DeployMate-data.db"
    return candidate if candidate.is_file() else None


def resolve_data_dir() -> Path:
    configured = os.getenv("DEPLOYMATE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent / "data"

    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base_dir / APP_NAME / f"{APP_VERSION}-{_release_build_id()}"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME / f"{APP_VERSION}-{_release_build_id()}"
    return Path.home() / ".local" / "share" / APP_NAME / f"{APP_VERSION}-{_release_build_id()}"


def resolve_resource_path(file_name: str) -> Path:
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_dir / file_name
