from datetime import date
from zipfile import ZipFile

from src.models import DailyReport, Expense, get_session
from src.services.daily_report_service import DailyReportService
from src.services.db_service import DatabaseService
from src.services.expense_service import ExpenseService
from src.services.project_service import ProjectService
from src.services.export_service import ExportService
from src.services.import_service import ImportService


def test_deleted_project_keeps_history_as_unassigned(tmp_path):
    DatabaseService(str(tmp_path / "history.db"))
    projects = ProjectService()
    reports = DailyReportService()
    expenses = ExpenseService()

    project = projects.create_project("待删除项目")
    report = reports.create_report(
        project.id, date(2026, 9, 10), work_content="部署记录", status="已完成"
    )
    expense = expenses.create_expense(
        project.id, date(2026, 9, 10), "交通", "12.50"
    )

    assert projects.delete_project(project.id) is True

    session = get_session()
    try:
        assert session.query(DailyReport).filter_by(id=report.id).one().project_id is None
        assert session.query(Expense).filter_by(id=expense.id).one().project_id is None
    finally:
        session.close()


def test_word_and_markdown_exports_are_structured_and_honor_sections(tmp_path):
    DatabaseService(str(tmp_path / "exports.db"))
    project = ProjectService().create_project(
        "导出测试项目", customer="客户甲", project_code="EXPORT-001"
    )
    DailyReportService().create_report(
        project.id, date(2026, 9, 10), work_content="完成安装步骤",
        problems="发现配置问题", solutions="调整配置后验证", status="已完成",
    )
    ExpenseService().create_expense(project.id, date(2026, 9, 10), "交通", "18.50")

    service = ExportService()
    word_path = tmp_path / "project.docx"
    markdown_path = tmp_path / "project.md"
    selected_path = tmp_path / "selected.md"
    service.export_projects([project.id], str(word_path), "docx")
    service.export_projects(
        [project.id], str(markdown_path), "md",
        include_projects=False, include_machines=False,
        include_reports=True, include_expenses=True,
    )
    service.export_projects(
        [project.id], str(selected_path), "md",
        include_projects=False, include_machines=False,
        include_reports=True, include_expenses=False,
    )

    markdown = markdown_path.read_text(encoding="utf-8")
    selected = selected_path.read_text(encoding="utf-8")
    assert "### SOP问题记录" in markdown
    assert "### 出差费用（合计 18.50 元）" in markdown
    assert "### 项目基本信息" not in selected
    assert "### 出差费用" not in selected
    with ZipFile(word_path) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "项目实施资料" in document_xml
    assert "完成安装步骤" in document_xml


def test_import_preserves_unknown_columns_and_source_headers(tmp_path):
    DatabaseService(str(tmp_path / "import.db"))
    source = tmp_path / "machines.xlsx"
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "项目甲"
    sheet.append(["销售", "徐明", "实施地点", "上海"])
    sheet.append(["管理网IP", "角色", "ssh端口号", "厂商"])
    sheet.append(["10.20.1.10", "master", 2222, "厂商甲"])
    workbook.save(source)

    groups = ImportService().read_file_groups(str(source))
    assert groups[0]["source_rows"][0]["ssh端口号"] == 2222
    assert groups[0]["source_rows"][0]["厂商"] == "厂商甲"
    assert groups[0]["preamble_rows"]
    assert groups[0]["rows"][0]["extra_info"] == '{"ssh端口号": 2222, "厂商": "厂商甲"}'
