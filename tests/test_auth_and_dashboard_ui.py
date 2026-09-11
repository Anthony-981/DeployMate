import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit

from src.models import base
from src.services.db_service import DatabaseService
from src.services.expense_service import ExpenseService
from src.services.project_service import ProjectService
from src.services.user_service import UserService
from src.ui.dialogs.login_dialog import LoginDialog
from src.ui.main_window import MainWindow
from src.ui.pages.home_page import TrendLineChart
from src.ui.pages.expense_page import ExpensePage
from src.ui.pages.import_page import ImportPage
from src.ui.widgets.common import ChineseContextMenuFilter, PaginationBar, build_chinese_context_menu


def test_login_dialog_initializes_admin_and_user_can_authenticate(tmp_path):
    DatabaseService(str(tmp_path / "auth-ui.db"))
    app = QApplication.instance() or QApplication([])
    dialog = LoginDialog()
    assert dialog.windowTitle() == "初始化管理员"
    assert dialog.submit_button.text() == "创建并进入"
    dialog.username_edit.setText("管理员")
    dialog.password_edit.setText("secret123")
    dialog.display_edit.setText("系统管理员")
    dialog.confirm_edit.setText("secret123")
    dialog.submit(True)
    assert dialog.result() == QDialog.Accepted
    assert dialog.user.role == "admin"

    service = UserService()
    guest = service.create_user("普通用户", "guest123", "普通用户", role="user")
    assert service.authenticate(guest.username, "guest123").role == "user"
    dialog.deleteLater()
    base.engine.dispose()


def test_main_window_has_chinese_logout_and_dashboard_sections(tmp_path):
    DatabaseService(str(tmp_path / "dashboard-ui.db"))
    app = QApplication.instance() or QApplication([])
    admin = UserService().create_user("admin", "secret123", "管理员", role="admin")
    window = MainWindow(admin)
    app.processEvents()
    logout_buttons = [
        button for button in window.findChildren(type(window.nav_buttons[0]))
        if button.text() == "退出登录"
    ]
    assert len(logout_buttons) == 1
    assert window.findChild(QLabel, "currentUserLabel").text() == "当前用户：管理员（admin）"
    home = window._ensure_page(0)
    assert home.recent_table.horizontalHeaderItem(0).text() == "项目名称"
    assert home.machine_table.horizontalHeaderItem(0).text() == "IP地址"
    window.logout()
    assert window._logging_out is True
    window.deleteLater()
    base.engine.dispose()


def test_ordinary_user_can_open_main_window(tmp_path):
    DatabaseService(str(tmp_path / "ordinary-ui.db"))
    app = QApplication.instance() or QApplication([])
    service = UserService()
    user = service.create_user("普通", "guest123", "普通用户", role="user")
    window = MainWindow(user)
    app.processEvents()
    assert window.current_user.role == "user"
    home = window._ensure_page(0)
    assert home.current_user is user
    assert home.loader.current_user is user
    window.logout()
    window.deleteLater()
    base.engine.dispose()


def test_expense_summary_shows_project_profit_rows(tmp_path):
    DatabaseService(str(tmp_path / "expense-summary-ui.db"))
    app = QApplication.instance() or QApplication([])
    project = ProjectService().create_project("湘南学院")
    expenses = ExpenseService()
    expenses.create_expense(
        project.id, date(2026, 9, 11), "考核费用", "2000",
        expense_category="考核费用",
    )
    expenses.create_expense(
        project.id, date(2026, 9, 11), "交通", "1000",
        expense_category="出差费用",
    )

    page = ExpensePage()
    app.processEvents()

    headers = [
        page.summary_table.horizontalHeaderItem(index).text()
        for index in range(page.summary_table.columnCount())
    ]
    values = [
        page.summary_table.item(0, index).text()
        for index in range(page.summary_table.columnCount())
    ]
    assert headers == ["项目", "总考核费用", "总出差费用", "实际利润", "记录数"]
    assert page.summary_table.rowCount() == 1
    assert values == ["湘南学院", "2000.00", "1000.00", "1000.00", "2"]
    expense_headers = [
        page.expense_table.horizontalHeaderItem(index).text()
        for index in range(page.expense_table.columnCount())
    ]
    assert "费用类型" not in expense_headers
    assert expense_headers[8:11] == ["考核费用", "出差费用", "本条利润"]
    line_values = {
        tuple(page.expense_table.item(row, index).text() for index in range(8, 11))
        for row in range(page.expense_table.rowCount())
    }
    assert ("2000.00", "0.00", "2000.00") in line_values
    assert ("0.00", "1000.00", "-1000.00") in line_values
    page.deleteLater()
    base.engine.dispose()


def test_chinese_context_menu_filter_and_pagination_labels(tmp_path):
    DatabaseService(str(tmp_path / "pagination-ui.db"))
    app = QApplication.instance() or QApplication([])
    edit = QLineEdit("测试")
    filter_object = ChineseContextMenuFilter(app)
    assert [action.text() for action in build_chinese_context_menu(edit).actions()] == [
        "撤销", "重做", "", "剪切", "复制", "粘贴", "删除", "全选"
    ]
    pager = PaginationBar(page_size=20)
    pager.set_total(652)
    pager.set_page(4)
    assert "更多" in [widget.text() for widget in pager.findChildren(type(pager.summary))]
    edit.deleteLater()
    base.engine.dispose()


def test_dashboard_zero_trend_and_import_page_with_user_context(tmp_path):
    DatabaseService(str(tmp_path / "zero-trend-ui.db"))
    app = QApplication.instance() or QApplication([])
    user = UserService().create_user("普通", "guest123", "普通用户", role="user")

    chart = TrendLineChart()
    chart.set_values([
        {"日期": "09-10", "项目数": 0, "机器数": 0, "导入文件数": 0},
        {"日期": "09-11", "项目数": 0, "机器数": 0, "导入文件数": 0},
    ])
    chart.resize(640, 280)
    chart.show()
    app.processEvents()
    chart.grab()

    page = ImportPage(user)
    assert page.current_user is user
    page.deleteLater()
    chart.deleteLater()
    base.engine.dispose()
