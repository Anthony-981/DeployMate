import sys
from pathlib import Path
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QToolTip
from PySide6.QtCore import Qt, QTimer

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ui.main_window import MainWindow
from src.services.db_service import DatabaseService
from src.ui.dialogs.login_dialog import LoginDialog
from src.config import APP_VERSION
from src.ui.widgets.common import APP_STYLESHEET, ChineseContextMenuFilter


def apply_light_palette(app: QApplication):
    """Windows dark mode can leak black palettes into Qt Fusion widgets."""
    palette = QPalette()
    light_colors = {
        QPalette.Window: QColor("#ffffff"),
        QPalette.WindowText: QColor("#0f1f3a"),
        QPalette.Base: QColor("#ffffff"),
        QPalette.AlternateBase: QColor("#f9fbfe"),
        QPalette.Text: QColor("#0f1f3a"),
        QPalette.Button: QColor("#edf4ff"),
        QPalette.ButtonText: QColor("#0f1f3a"),
        QPalette.ToolTipBase: QColor("#ffffff"),
        QPalette.ToolTipText: QColor("#24344f"),
        QPalette.Highlight: QColor("#3f7dff"),
        QPalette.HighlightedText: QColor("#ffffff"),
        QPalette.PlaceholderText: QColor("#8593a8"),
        QPalette.Link: QColor("#3f7dff"),
        QPalette.BrightText: QColor("#ffffff"),
    }
    for group in (
        QPalette.Active,
        QPalette.Inactive,
        QPalette.Disabled,
    ):
        for role, color in light_colors.items():
            palette.setColor(group, role, color)
        if group == QPalette.Disabled:
            palette.setColor(group, QPalette.Text, QColor("#98a4b5"))
            palette.setColor(group, QPalette.WindowText, QColor("#98a4b5"))
            palette.setColor(group, QPalette.ButtonText, QColor("#98a4b5"))
    app.setPalette(palette)

def main():
    # 初始化数据库
    db_service = DatabaseService()
    print(f"数据库初始化完成: {db_service.db_path} ({db_service.db_mode})")
    
    # New installations start empty; fixtures are only created explicitly by tests.
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName(f"DeployMate {APP_VERSION}")
    app.setQuitOnLastWindowClosed(False)
    
    # 设置全局样式
    app.setStyle("Fusion")
    apply_light_palette(app)
    app.setStyleSheet(APP_STYLESHEET)

    # Windows 深色模式可能让系统 tooltip 使用深色底，这里强制表格悬停提示为浅色。
    tooltip_palette = QPalette()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        tooltip_palette.setColor(group, QPalette.ToolTipBase, QColor("#ffffff"))
        tooltip_palette.setColor(group, QPalette.ToolTipText, QColor("#24344f"))
        tooltip_palette.setColor(group, QPalette.Window, QColor("#ffffff"))
        tooltip_palette.setColor(group, QPalette.WindowText, QColor("#24344f"))
    QToolTip.setPalette(tooltip_palette)
    
    context_menu_filter = ChineseContextMenuFilter(app)
    app.installEventFilter(context_menu_filter)

    # 本地应用启动时登录；退出登录后回到登录窗口，而不是直接结束程序。
    while True:
        login = LoginDialog()
        if login.exec() != QDialog.Accepted:
            return
        window = MainWindow(current_user=login.user)
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        QTimer.singleShot(300, window.raise_)
        QTimer.singleShot(300, window.activateWindow)
        app.exec()
        if not getattr(window, "_logging_out", False):
            return

if __name__ == "__main__":
    main()
