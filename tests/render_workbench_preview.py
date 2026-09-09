import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.models import base
from src.services.db_service import DatabaseService
from src.services.machine_service import MachineService
from src.services.project_service import ProjectService
from src.ui.pages.import_page import ImportPage
from src.ui.pages.machine_page import MachinePage
from src.ui.widgets.common import APP_STYLESHEET


def run():
    db_path = Path(tempfile.gettempdir()) / "deploymate_workbench_preview.db"
    db_path.unlink(missing_ok=True)
    DatabaseService(str(db_path), "dev")
    project = ProjectService().create_project(name="湘南学院", sales="李化敏", location="湖南")
    MachineService().create_machine(
        project.id, "10.8.51.53", role="master", business_ip="10.8.51.53",
        username="root", password="Server-2026", gpu_count="8", gpu_model="RTX 3090",
    )

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    machine = MachinePage()
    importer = ImportPage()
    pages = [machine, importer]
    for page in pages:
        page.resize(1440, 760)
        page.show()
        app.processEvents()

    output = QImage(1440, 1520, QImage.Format_ARGB32)
    output.fill("#eef3f9")
    painter = QPainter(output)
    painter.drawImage(0, 0, machine.grab().toImage())
    painter.drawImage(0, 760, importer.grab().toImage())
    painter.end()
    output.save(str(Path(__file__).resolve().parent.parent / "docs" / "deploymate-workbench-preview.png"))

    for page in pages:
        page.close()
    base.engine.dispose()
    db_path.unlink(missing_ok=True)
    print("Workbench preview: OK")


if __name__ == "__main__":
    run()
