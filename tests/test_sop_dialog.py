import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLabel

from src.models import base
from src.services.db_service import DatabaseService
from src.services.project_service import ProjectService
from src.ui.pages.daily_page import DailyPage


def run():
    db_path = Path(tempfile.gettempdir()) / "deploymate_sop_dialog.db"
    db_path.unlink(missing_ok=True)
    DatabaseService(str(db_path), "dev")
    ProjectService().create_project(name="项目甲", project_code="SOP-001")
    ProjectService().create_project(name="项目乙", project_code="SOP-002")
    app = QApplication.instance() or QApplication([])
    page = DailyPage()

    def inspect_dialog():
        dialog = next(widget for widget in app.topLevelWidgets() if isinstance(widget, QDialog) and widget.isVisible())
        combos = dialog.findChildren(QComboBox)
        assert combos and combos[0].count() == 2
        combos[0].setCurrentIndex(1)
        assert combos[0].currentData() is not None
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        order = ["项目 *", "日期 *", "遇到的问题 *", "解决办法和步骤 *", "后续建议", "备注", "状态"]
        positions = [labels.index(text) for text in order]
        assert positions == sorted(positions)
        dialog.reject()

    QTimer.singleShot(100, inspect_dialog)
    page.open_report_dialog()
    page.close()
    base.engine.dispose()
    db_path.unlink(missing_ok=True)
    print("SOP dialog: PASS")


if __name__ == "__main__":
    run()
