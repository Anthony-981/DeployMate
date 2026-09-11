from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from src.config import resolve_resource_path
from src.services.user_service import UserService
from src.ui.widgets.common import APP_STYLESHEET, make_button


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_service = UserService()
        self.user = None
        first_run = not self.user_service.has_users()
        self.setWindowTitle("初始化管理员" if first_run else "登录 DeployMate")
        self.setModal(True)
        self.setFixedWidth(440)
        self.setStyleSheet(APP_STYLESHEET)

        logo_path = resolve_resource_path("logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(16)
        if logo_path.exists():
            logo_label = QLabel()
            logo_label.setObjectName("loginLogo")
            logo_label.setAlignment(Qt.AlignCenter)
            logo_label.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
            layout.addWidget(logo_label)
        title = QLabel("创建管理员账户" if first_run else "登录 DeployMate")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 23px; font-weight: 800; color: #0f1f3a;")
        layout.addWidget(title)
        subtitle = QLabel(
            "首次使用请创建本地管理员账户。" if first_run
            else "请输入用户名和密码后进入本地工作台。"
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #627189;")
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("例如：admin")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("请输入密码")
        form.addRow("用户名", self.username_edit)
        form.addRow("密码", self.password_edit)
        if first_run:
            self.display_edit = QLineEdit()
            self.display_edit.setPlaceholderText("例如：系统管理员")
            form.addRow("显示名称", self.display_edit)
            self.confirm_edit = QLineEdit()
            self.confirm_edit.setEchoMode(QLineEdit.Password)
            self.confirm_edit.setPlaceholderText("再次输入密码")
            form.addRow("确认密码", self.confirm_edit)
        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #bd3f3f;")
        layout.addWidget(self.error_label)
        actions = QVBoxLayout()
        self.submit_button = make_button("创建并进入" if first_run else "登录", True)
        self.submit_button.clicked.connect(lambda: self.submit(first_run))
        actions.addWidget(self.submit_button)
        layout.addLayout(actions)
        self.password_edit.returnPressed.connect(self.submit_button.click)

    def submit(self, first_run: bool):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if first_run:
            if password != self.confirm_edit.text():
                self.error_label.setText("两次输入的密码不一致")
                return
            try:
                self.user = self.user_service.create_user(
                    username, password, self.display_edit.text().strip() or username, role="admin"
                )
            except Exception as exc:
                self.error_label.setText(str(exc))
                return
        else:
            self.user = self.user_service.authenticate(username, password)
            if not self.user:
                self.error_label.setText("用户名或密码不正确，或用户已停用")
                return
        self.accept()
