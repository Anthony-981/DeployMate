import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from src.models import base
from src.services.db_service import DatabaseService
from src.services.machine_service import MachineService
from src.services.project_service import ProjectService
from src.ui.pages.import_page import ImportPage


def run():
    db_path = Path(tempfile.gettempdir()) / "deploymate_import_repair_ui.db"
    db_path.unlink(missing_ok=True)
    DatabaseService(str(db_path), "dev")
    project = ProjectService().create_project(name="修正项目", project_code="FIX-001")
    app = QApplication.instance() or QApplication([])
    page = ImportPage()
    page.pending_errors = [{
        "row": 2,
        "message": "测试失败",
        "project_id": project.id,
        "data": {"business_ip": "10.30.1.10", "role": "master", "username": "root"},
    }]
    page.conflict_rows = [[2, "错误", "", "测试失败", "", "未导入"]]
    page.batch_fix_errors()
    app.processEvents()

    machines = MachineService().get_machines_by_project(project.id)
    assert len(machines) == 1
    assert machines[0].ip == "10.30.1.10"
    assert machines[0].role == "master"
    assert page.pending_errors == []
    assert not page.fix_btn.isEnabled()
    assert not page.batch_fix_btn.isEnabled()
    assert page.repair_history[-1]["status"] == "批量修正"

    page.close()
    base.engine.dispose()
    db_path.unlink(missing_ok=True)
    print("Import repair UI: PASS")


if __name__ == "__main__":
    run()
