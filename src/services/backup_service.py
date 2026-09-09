from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
from zipfile import ZipFile
from PySide6.QtCore import QSettings
from src.models import base

from src.config import resolve_db_path


class BackupService:
    def backup_now(self, backup_dir: str | None = None, file_format: str = "db") -> str:
        source = Path(resolve_db_path())
        if not source.exists():
            raise FileNotFoundError(f"数据库不存在：{source}")
        configured = QSettings("DeployMate", "DeployMate").value("backup_dir", "")
        target_dir = Path(backup_dir or configured or source.parent / "backups")
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".xlsx" if file_format == "xlsx" else ".db"
        target = target_dir / f"deploymate_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
        if suffix == ".xlsx":
            from src.services.export_service import ExportService
            ExportService().export_projects(None, str(target), "xlsx")
        else:
            shutil.copy2(source, target)
        return str(target)

    def verify(self, backup_path: str) -> tuple[bool, str]:
        """Verify a backup file can be opened before it is reported as usable."""
        path = Path(backup_path)
        if not path.exists() or path.stat().st_size == 0:
            return False, "文件不存在或为空"
        try:
            if path.suffix.lower() == ".db":
                with sqlite3.connect(path) as connection:
                    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
                return result == "ok", str(result)
            if path.suffix.lower() == ".xlsx":
                with ZipFile(path) as archive:
                    bad_file = archive.testzip()
                return bad_file is None, "文件结构正常" if bad_file is None else f"损坏文件：{bad_file}"
            return False, "不支持的备份格式"
        except Exception as exc:
            return False, str(exc)

    def prune(self, backup_dir: str | None = None, keep_count: int = 10) -> int:
        settings = QSettings("DeployMate", "DeployMate")
        source = Path(resolve_db_path())
        directory = Path(backup_dir or settings.value("backup_dir", "") or source.parent / "backups")
        files = sorted(
            [*directory.glob("deploymate_*.db"), *directory.glob("deploymate_*.xlsx")],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for path in files[max(1, int(keep_count)):]:
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def restore(self, source_path: str) -> str:
        source = Path(source_path)
        target = Path(resolve_db_path())
        if not source.exists() or source.suffix.lower() != ".db":
            raise ValueError("请选择有效的 SQLite .db 备份文件")
        if source.resolve() == target.resolve():
            raise ValueError("不能恢复当前正在使用的数据库文件")
        if base.engine is not None:
            base.engine.dispose()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return str(target)
