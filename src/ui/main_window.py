from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, QSettings, Signal
from PySide6.QtGui import QFont
from PySide6.QtGui import QIcon
from src.config import resolve_resource_path
from src.ui.widgets.common import APP_STYLESHEET
from src.services.backup_service import BackupService
from src.config import APP_VERSION
from datetime import datetime, timedelta
from threading import Lock, Thread

class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.setWindowTitle(f"DeployMate {APP_VERSION} - 运维实施工程师记录助手")
        self.setMinimumSize(1100, 720)
        logo_path = resolve_resource_path("logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.setStyleSheet(APP_STYLESHEET)
        
        self.init_ui()
        self._backup_lock = Lock()
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self._run_scheduled_backup)
        self.backup_timer.start(60 * 1000)
        QTimer.singleShot(1500, self._run_scheduled_backup)
    
    def init_ui(self):
        # 顶部栏与内容区按首页参考图组织，导航默认收起。
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(54)
        top_bar.setStyleSheet("""
            QFrame#topBar {
                background: #ffffff;
                border-bottom: 1px solid #dfe8f5;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 0, 12, 0)
        menu_button = QToolButton()
        menu_button.setText("☰")
        menu_button.setToolTip("打开或收起导航菜单")
        menu_button.setFixedSize(34, 34)
        menu_button.setStyleSheet("""
            QToolButton { color: #31588f; border: none; font-size: 22px; }
            QToolButton:hover { background: #edf4ff; border-radius: 8px; }
        """)
        top_layout.addWidget(menu_button)
        top_title = QLabel("DeployMate")
        top_title.setStyleSheet("font-size: 16px; font-weight: 900; color: #17417e;")
        top_layout.addWidget(top_title)
        top_layout.addStretch()
        display_name = getattr(self.current_user, "display_name", "") or "本地用户"
        username = getattr(self.current_user, "username", "") or "未登录"
        top_account = QLabel(f"当前用户：{display_name}（{username}）")
        top_account.setObjectName("currentUserLabel")
        top_account.setStyleSheet("color: #49658b; font-weight: 700; padding: 0 10px;")
        top_layout.addWidget(top_account)
        top_logout = QPushButton("退出登录")
        top_logout.setFixedHeight(32)
        top_logout.setStyleSheet("""
            QPushButton {
                background: #edf4ff; color: #315dd3;
                border: 1px solid #d8e4fb; border-radius: 8px;
                padding: 0 12px; font-weight: 700;
            }
            QPushButton:hover { background: #e3edff; }
        """)
        top_logout.clicked.connect(self.logout)
        top_layout.addWidget(top_logout)
        root_layout.addWidget(top_bar)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(16, 14, 16, 16)
        body_layout.setSpacing(14)
        root_layout.addLayout(body_layout, 1)

        nav_frame = self.create_nav_bar()
        nav_frame.setVisible(False)
        menu_button.clicked.connect(lambda: nav_frame.setVisible(not nav_frame.isVisible()))
        body_layout.addWidget(nav_frame)

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
        body_layout.addWidget(self.content_shell, 1)
        
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

    def logout(self):
        self._logging_out = True
        self.close()
        QApplication.instance().quit()
    
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
        if not self._backup_lock.acquire(blocking=False):
            return
        file_format = "xlsx" if str(settings.value("backup_format", "")).startswith("Excel") else "db"
        keep_count = max(1, int(settings.value("backup_retention", 10) or 10))

        def backup_in_background():
            try:
                service = BackupService()
                path = service.backup_now(file_format=file_format)
                service.prune(keep_count=keep_count)
                worker_settings = QSettings("DeployMate", "DeployMate")
                worker_settings.setValue("last_backup_path", path)
                worker_settings.setValue("last_backup_at", datetime.now().isoformat(timespec="seconds"))
                worker_settings.sync()
            except Exception:
                pass
            finally:
                self._backup_lock.release()

        Thread(target=backup_in_background, name="deploymate-backup", daemon=True).start()

    def closeEvent(self, event):
        """Database writes are committed immediately; scheduled backups run off the UI thread."""
        if not getattr(self, "_logging_out", False):
            QApplication.instance().quit()
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
            lambda: HomePage(self.current_user),
            lambda: ProjectPage(self.current_user),
            lambda: MachinePage(self.current_user),
            lambda: ImportPage(self.current_user),
            lambda: DailyPage(self.current_user),
            lambda: ExpensePage(self.current_user),
            lambda: ExportPage(self.current_user),
            lambda: SettingsPage(self.current_user, on_password_changed=self.logout),
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
