import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication, QPushButton

from src.services.db_service import DatabaseService
from src.services.project_service import ProjectService
from src.models import base
from src.ui.pages.import_page import ImportPage
from src.ui.pages.machine_page import MachinePage
from src.ui.pages.project_page import ProjectPage


def run():
    database = Path(tempfile.gettempdir()) / "deploymate_project_import_ui.db"
    database.unlink(missing_ok=True)
    DatabaseService(str(database), "dev")
    project = ProjectService().create_project(
        name="SCM",
        project_code="SCM-001",
        sales="徐明生",
    )
    assert project.sales == "徐明生"

    app = QApplication.instance() or QApplication([])
    import_page = ImportPage()
    project_page = ProjectPage()
    machine_page = MachinePage()
    import_page.import_completed.connect(machine_page.select_project)
    import_page.resize(960, 900)
    import_page.show()
    app.processEvents()

    button_texts = [button.text() for button in import_page.findChildren(QPushButton)]
    assert "选择文件" not in button_texts
    assert import_page.import_btn.text() == "确认导入"
    assert "点击此区域选择文件" in import_page.hint.text()
    headers = [
        project_page.project_table.horizontalHeaderItem(index).text()
        for index in range(project_page.project_table.columnCount())
    ]
    assert "销售" in headers
    assert "版本" not in headers
    assert import_page.import_btn.isVisible()
    assert import_page.import_btn.mapTo(import_page, import_page.import_btn.rect().topRight()).x() < import_page.width()

    workbook = Workbook()
    first = workbook.active
    first.title = "项目一"
    first.append(["项目一"])
    first.append(["角色", "业务网IP", "用户名", "GPU数量"])
    first.append(["管理节点", "10.20.1.1", "root", 0])
    second = workbook.create_sheet("项目二")
    second.append(["项目二"])
    second.append(["角色", "集群网IP", "用户名", "GPU数量"])
    second.append(["计算节点", "10.20.2.1", "root", 8])
    workbook_path = Path(tempfile.gettempdir()) / "deploymate_ui_multi_sheet.xlsx"
    workbook.save(workbook_path)
    groups = import_page.import_service.read_file_groups(workbook_path)
    import_page.current_file_path = str(workbook_path)
    import_page.current_groups = groups
    import_page.current_rows = [row for group in groups for row in group["rows"]]
    import_page.auto_project_check.setEnabled(True)
    import_page.auto_project_check.setChecked(True)
    import_page.import_current_file()

    app.processEvents()
    assert machine_page.project_filter.currentText() == "全部项目"
    assert machine_page.machine_table.rowCount() == 2
    machine_headers = [
        machine_page.machine_table.horizontalHeaderItem(index).text()
        for index in range(machine_page.machine_table.columnCount())
    ]
    assert "所属项目" in machine_headers
    project_column = machine_headers.index("所属项目")
    visible_projects = {
        machine_page.machine_table.item(row, project_column).text()
        for row in range(machine_page.machine_table.rowCount())
    }
    assert any("项目一" in label for label in visible_projects)
    assert any("项目二" in label for label in visible_projects)
    imported_projects = ProjectService().get_all_projects()
    imported_customers = {project.customer for project in imported_projects}
    assert "项目一" in imported_customers
    assert "项目二" in imported_customers
    assert len(import_page.import_service.get_import_history()) == 2

    import_page.close()
    project_page.close()
    machine_page.close()
    workbook_path.unlink(missing_ok=True)
    base.engine.dispose()
    database.unlink(missing_ok=True)
    print("OK")


if __name__ == "__main__":
    run()
