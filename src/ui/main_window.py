from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QFont
from PySide6.QtGui import QIcon
from src.config import resolve_resource_path
from src.ui.widgets.common import APP_STYLESHEET
from src.services.backup_service import BackupService
from src.config import APP_VERSION
from datetime import datetime, timedelta

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DeployMate {APP_VERSION} - 运维实施工程师记录助手")
        self.setMinimumSize(1100, 720)
        logo_path = resolve_resource_path("logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet(APP_STYLESHEET)
        
        self.init_ui()
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self._run_scheduled_backup)
        self.backup_timer.start(60 * 1000)
        QTimer.singleShot(1500, self._run_scheduled_backup)
    
    def init_ui(self):
        # 主容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(18)
        
        # 左侧导航栏
        nav_frame = self.create_nav_bar()
        main_layout.addWidget(nav_frame)
        
        # 右侧内容区
        self.content_shell = QFrame()
        self.content_shell.setObjectName("contentShell")
        self.content_shell.setStyleSheet("""
            QFrame#contentShell {
                background: #f8fbff;
                border: 1px solid #dbe5f2;
                border-radius: 24px;
            }
        """)
        content_layout = QVBoxLayout(self.content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: transparent;")
        content_layout.addWidget(self.content_stack)
        main_layout.addWidget(self.content_shell)
        
        # 添加页面（暂时用占位符）
        self.add_pages()
        self.content_stack.setCurrentIndex(0)
    
    def create_nav_bar(self):
        """创建左侧导航栏"""
        nav_frame = QFrame()
        nav_frame.setFixedWidth(270)
        nav_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #17213f, stop:1 #223d84);
                border-radius: 24px;
            }
        """)
        
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(18, 22, 18, 22)
        nav_layout.setSpacing(0)
        
        # 品牌标题
        brand_label = QLabel("DeployMate")
        brand_label.setStyleSheet("color: white; font-size: 27px; font-weight: 800;")
        nav_layout.addWidget(brand_label)

        sub_label = QLabel("运维实施工程师记录助手")
        sub_label.setStyleSheet("color: #aabcec; font-size: 13px; margin-top: 6px;")
        nav_layout.addWidget(sub_label)

        nav_layout.addSpacing(22)
        
        # 导航按钮
        nav_items = [
            ("首页", 0),
            ("项目管理", 1),
            ("机器信息", 2),
            ("导入 / 合并", 3),
            ("SOP问题记录", 4),
            ("出差费用", 5),
            ("导出资料", 6),
            ("设置", 7),
        ]
        
        self.nav_buttons = []
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self.get_nav_button_style(False))
            btn.clicked.connect(lambda checked, idx=index: self.switch_page(idx))
            nav_layout.addWidget(btn)
            nav_layout.addSpacing(7)
            self.nav_buttons.append(btn)
        
        nav_layout.addStretch()
        
        # 默认选中首页
        self.nav_buttons[0].setStyleSheet(self.get_nav_button_style(True))
        
        return nav_frame
    
    def get_nav_button_style(self, active: bool):
        """获取导航按钮样式"""
        if active:
            return """
                QPushButton {
                    background: rgba(255, 255, 255, 0.14);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 14px;
                    text-align: left;
                    padding-left: 15px;
                    font-weight: bold;
                    font-size: 15px;
                }
                QPushButton:hover { background: rgba(255, 255, 255, 0.18); }
            """
        else:
            return """
                QPushButton {
                    background: transparent;
                    color: #c8d7fb;
                    border: none;
                    border-radius: 14px;
                    text-align: left;
                    padding-left: 15px;
                    font-weight: bold;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.08);
                    color: white;
                }
            """
    
    def switch_page(self, index: int):
        """切换页面"""
        self._ensure_page(index)
        self.content_stack.setCurrentIndex(index)
        if hasattr(self, "pages") and 0 <= index < len(self.pages) and self.pages[index] is not None:
            reload_data = getattr(self.pages[index], "reload_data", None)
            if callable(reload_data):
                reload_data()
        
        # 更新导航按钮样式
        for i, btn in enumerate(self.nav_buttons):
            btn.setStyleSheet(self.get_nav_button_style(i == index))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(300, self._bring_to_front)

    def _bring_to_front(self):
        self.raise_()
        self.activateWindow()

    def _run_scheduled_backup(self):
        settings = QSettings("DeployMate", "DeployMate")
        frequency = settings.value("backup_frequency", "每天")
        if frequency == "关闭":
            return
        last_value = settings.value("last_backup_at", "")
        try:
            last = datetime.fromisoformat(last_value) if last_value else None
        except ValueError:
            last = None
        interval = timedelta(days=7 if frequency == "每周" else 1)
        if last and datetime.now() - last < interval:
            return
        try:
            file_format = "xlsx" if str(settings.value("backup_format", "")).startswith("Excel") else "db"
            path = BackupService().backup_now(file_format=file_format)
            keep_count = int(settings.value("backup_retention", 10) or 10)
            BackupService().prune(keep_count=max(1, keep_count))
            settings.setValue("last_backup_path", path)
            settings.setValue("last_backup_at", datetime.now().isoformat(timespec="seconds"))
            settings.sync()
        except Exception:
            # Automatic backup must never prevent the application from opening.
            return

    def closeEvent(self, event):
        """Persist a final backup on normal close when automatic backup is enabled."""
        settings = QSettings("DeployMate", "DeployMate")
        if settings.value("backup_frequency", "每天") != "关闭":
            try:
                file_format = "xlsx" if str(settings.value("backup_format", "")).startswith("Excel") else "db"
                path = BackupService().backup_now(file_format=file_format)
                keep_count = int(settings.value("backup_retention", 10) or 10)
                BackupService().prune(keep_count=max(1, keep_count))
                settings.setValue("last_backup_path", path)
                settings.setValue("last_backup_at", datetime.now().isoformat(timespec="seconds"))
                settings.sync()
            except Exception:
                pass
        super().closeEvent(event)
    
    def add_pages(self):
        """Create lightweight page shells; expensive pages load on first visit."""
        from src.ui.pages.home_page import HomePage
        from src.ui.pages.project_page import ProjectPage
        from src.ui.pages.machine_page import MachinePage
        from src.ui.pages.import_page import ImportPage
        from src.ui.pages.daily_page import DailyPage
        from src.ui.pages.expense_page import ExpensePage
        from src.ui.pages.export_page import ExportPage
        from src.ui.pages.settings_page import SettingsPage

        self.page_factories = [
            HomePage, ProjectPage, MachinePage, ImportPage,
            DailyPage, ExpensePage, ExportPage, SettingsPage,
        ]
        self.pages = [None] * len(self.page_factories)
        for _index in self.page_factories:
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            placeholder = QLabel("正在准备页面…")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #7a8aa3; font-size: 15px; padding: 80px;")
            scroll.setWidget(placeholder)
            self.content_stack.addWidget(scroll)

        self._ensure_page(0)

    def _ensure_page(self, index: int):
        if not (0 <= index < len(self.page_factories)):
            return None
        if self.pages[index] is not None:
            return self.pages[index]
        page = self.page_factories[index]()
        self.pages[index] = page
        scroll = self.content_stack.widget(index)
        scroll.setWidget(page)
        if index == 3:
            page.import_completed.connect(self._refresh_machine_after_import)
        return page

    def _refresh_machine_after_import(self, project_id: int):
        machine_page = self._ensure_page(2)
        machine_page.select_project(project_id if project_id else None)
        self.switch_page(2)

    def refresh_all_pages(self):
        for index in range(len(getattr(self, "page_factories", []))):
            page = self._ensure_page(index)
            reload_data = getattr(page, "reload_data", None)
            if callable(reload_data):
                reload_data()
