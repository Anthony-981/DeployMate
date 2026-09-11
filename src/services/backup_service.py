from datetime import datetime
import os
from pathlib import Path
import sqlite3
import shutil
import sys
import tempfile
from zipfile import ZipFile
from PySide6.QtCore import QSettings
from src.models import base

from src.config import resolve_db_path


class BackupService:
    def export_portable_package(self, target_path: str) -> str:
        """Create a private package containing the current executable and data."""
        if not getattr(sys, "frozen", False):
            raise RuntimeError("请在已打包的软件中生成共享包")
        executable = Path(sys.executable).resolve()
        database = Path(resolve_db_path())
        target = Path(target_path).expanduser().resolve()
        if not executable.is_file():
            raise FileNotFoundError(f"程序文件不存在：{executable}")
        if not database.is_file():
            raise FileNotFoundError(f"数据库不存在：{database}")
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="deploymate-share-") as staging:
            staging_dir = Path(staging)
            app_name = executable.name
            shutil.copy2(executable, staging_dir / app_name)
            # Use SQLite's backup API so WAL state is folded into one portable file.
            shared_db = staging_dir / "DeployMate-data.db"
            source_db = sqlite3.connect(database)
            target_db = sqlite3.connect(shared_db)
            try:
                source_db.backup(target_db, pages=1024)
            finally:
                target_db.close()
                source_db.close()
            readme = staging_dir / "共享数据包说明.txt"
            readme.write_text(
                "解压后双击程序即可使用，数据库已随包加载，无需重新创建管理员。\n"
                "此文件包含真实业务数据和账号信息，请勿上传到公开网站。\n",
                encoding="utf-8",
            )
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.unlink(missing_ok=True)
            try:
                with ZipFile(temporary, "w") as archive:
                    for path in staging_dir.iterdir():
                        archive.write(path, path.name)
                os.replace(temporary, target)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        return str(target)

    def backup_now(self, backup_dir: str | None = None, file_format: str = "db") -> str:
        source = Path(resolve_db_path())
        if not source.exists():
            raise FileNotFoundError(f"数据库不存在：{source}")
        configured = QSettings("DeployMate", "DeployMate").value("backup_dir", "")
        target_dir = Path(backup_dir or configured or source.parent / "backups")
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".xlsx" if file_format == "xlsx" else ".db"
        target = target_dir / f"deploymate_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
        temporary = target.with_name(f".{target.stem}.tmp{target.suffix}")
        temporary.unlink(missing_ok=True)
        try:
            if suffix == ".xlsx":
                from src.services.export_service import ExportService
                ExportService().export_projects(None, str(temporary), "xlsx")
            else:
                with sqlite3.connect(source) as source_db, sqlite3.connect(temporary) as target_db:
                    source_db.backup(target_db, pages=1024)
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
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
        with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
            source_db.backup(target_db, pages=1024)
        return str(target)
