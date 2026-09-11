from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QLineEdit, QComboBox, QSpinBox, QTextBrowser, QHBoxLayout,
    QTableWidgetItem, QMessageBox,
)
from src.services.backup_service import BackupService
from src.services.user_service import UserService
from src.ui.widgets.common import (
    FormDialog, PasswordLineEdit, make_button, make_compact_form, make_page,
    make_panel, make_table, show_toast, confirm_action,
)

class SettingsPage:
    def __new__(cls, current_user=None, on_password_changed=None):
        page, layout, head = make_page("设置", "配置本地数据目录、备份策略、导出规则和安全选项。")
        save_button = make_button("保存设置", True)
        head.addWidget(save_button)
        backup_button = make_button("立即备份")
        head.addWidget(backup_button)
        restore_button = make_button("恢复数据库")
        head.addWidget(restore_button)
        verify_button = make_button("校验备份")
        head.addWidget(verify_button)

        settings = QSettings("DeployMate", "DeployMate")

        panel, panel_layout = make_panel("本地数据管理")
        data_dir_edit = QLineEdit(settings.value("backup_dir", ""))
        data_dir_edit.setMaxLength(260)
        choose_dir_button = make_button("选择目录")
        backup = QComboBox()
        backup.setFocusPolicy(Qt.NoFocus)
        backup.addItems(["每天", "每周", "关闭"])
        backup.setCurrentText(settings.value("backup_frequency", "每天"))
        backup_format = QComboBox()
        backup_format.addItems(["SQLite 数据库 (.db)", "Excel 表格 (.xlsx)"])
        backup_format.setCurrentText(settings.value("backup_format", "SQLite 数据库 (.db)"))
        retention = QSpinBox()
        retention.setRange(1, 999)
        retention.setValue(int(settings.value("backup_retention", 10)))
        retention.setButtonSymbols(QSpinBox.UpDownArrows)
        retention.setMinimumWidth(150)
        retention.setStyleSheet("""
            QSpinBox {
                background: #ffffff;
                color: #24344f;
                border: 1px solid #cbd9eb;
                border-radius: 8px;
                padding: 6px 34px 6px 10px;
                min-height: 34px;
            }
            QSpinBox:focus { border: 1px solid #4b83ff; }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 26px;
                background: #eef4ff;
                border: 0;
                border-left: 1px solid #d6e2f3;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #dce9ff; }
            QSpinBox::up-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 6px solid #315dd3; }
            QSpinBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #315dd3; }
        """)
        last_backup = QLabel()
        last_backup.setStyleSheet("color: #52627a; padding: 8px 0;")
        last_path = settings.value("last_backup_path", "")
        last_time = settings.value("last_backup_at", "")
        last_backup.setText(f"最近备份：{last_time or '尚未备份'}\n文件：{last_path or '未生成'}")
        password = QComboBox()
        password.setFocusPolicy(Qt.NoFocus)
        password.addItems(["默认导出密码", "不导出密码"])
        password.setCurrentText(settings.value("password_export", "默认导出密码"))
        panel_layout.addLayout(make_compact_form([
            ("备份目录（空=数据库目录）", data_dir_edit), ("自动备份", backup),
            ("备份文件格式", backup_format), ("密码导出", password),
            ("保留备份数量", retention),
        ], columns=2, field_width=380))
        panel_layout.addWidget(choose_dir_button)
        panel_layout.addWidget(last_backup)
        help_label = QTextBrowser()
        help_label.setOpenExternalLinks(False)
        help_label.setMaximumHeight(150)
        help_label.setStyleSheet(
            "QTextBrowser { background: #f7faff; color: #536783; border: 1px solid #dce7f5; "
            "border-radius: 8px; padding: 8px; }"
        )
        help_label.setHtml(
            "<b>设置说明</b><br>"
            "备份目录为空时，文件会保存在数据库目录下的 backups 文件夹。"
            "自动备份会在软件运行期间按设定频率检查。<br>"
            "SQLite 备份适合完整恢复；Excel 备份适合查看和归档。"
            "恢复数据库前请先关闭其他正在使用该数据库的程序。<br>"
            "保留数量按备份文件总数计算；立即备份完成后会自动校验文件完整性。<br>"
            "“不导出密码”只影响备份/导出文件，不会清除数据库中的密码。"
        )
        data_dir_edit.setToolTip("备份文件保存位置；留空时使用当前数据库目录下的 backups 文件夹。")
        backup.setToolTip("自动备份只在软件运行期间检查。关闭表示不自动执行。")
        backup_format.setToolTip("SQLite 可恢复完整数据库；Excel 适合阅读、归档和分享。")
        password.setToolTip("仅影响 Excel 备份和项目导出，不会修改数据库中的密码。")
        retention.setToolTip("只保留最近的备份文件，至少保留 1 个。")
        choose_dir_button.setToolTip("选择备份文件夹")
        layout.addWidget(panel)

        def save():
            settings.setValue("backup_dir", data_dir_edit.text().strip())
            settings.setValue("backup_frequency", backup.currentText())
            settings.setValue("backup_format", backup_format.currentText())
            settings.setValue("password_export", password.currentText())
            settings.setValue("backup_retention", retention.value())
            settings.sync()
            show_toast(page, "设置已保存，自动备份将在下次检查时按频率执行")

        def backup_now():
            try:
                file_format = "xlsx" if backup_format.currentText().startswith("Excel") else "db"
                path = BackupService().backup_now(file_format=file_format)
                from datetime import datetime
                settings.setValue("last_backup_at", datetime.now().isoformat(timespec="seconds"))
                settings.setValue("last_backup_path", path)
                settings.sync()
                BackupService().prune(keep_count=retention.value())
                valid, detail = BackupService().verify(path)
                if not valid:
                    raise RuntimeError(f"备份校验失败：{detail}")
                last_backup.setText(f"最近备份：{settings.value('last_backup_at')}\n文件：{path}")
                show_toast(page, f"备份成功并已校验：{path}")
            except Exception as exc:
                show_toast(page, f"备份失败：{exc}", False)

        save_button.clicked.connect(save)
        backup_button.clicked.connect(backup_now)

        def restore_db():
            source, _ = QFileDialog.getOpenFileName(page, "选择 SQLite 备份", "", "SQLite 数据库 (*.db)")
            if not source or not confirm_action(page, "确认恢复", "恢复后当前数据库将被覆盖，并立即刷新所有页面。确定继续吗？"):
                return
            try:
                target = BackupService().restore(source)
                refresh = getattr(page.window(), "refresh_all_pages", None)
                if callable(refresh):
                    refresh()
                show_toast(page, f"数据库已恢复并刷新页面：{target}")
            except Exception as exc:
                show_toast(page, f"恢复失败：{exc}", False)

        restore_button.clicked.connect(restore_db)

        def choose_backup_dir():
            directory = QFileDialog.getExistingDirectory(page, "选择备份目录", data_dir_edit.text().strip())
            if directory:
                data_dir_edit.setText(directory)

        def verify_backup():
            source, _ = QFileDialog.getOpenFileName(page, "选择备份文件", data_dir_edit.text().strip(), "备份文件 (*.db *.xlsx)")
            if not source:
                return
            valid, detail = BackupService().verify(source)
            show_toast(page, f"备份校验通过：{detail}" if valid else f"备份校验失败：{detail}", valid)

        choose_dir_button.clicked.connect(choose_backup_dir)
        verify_button.clicked.connect(verify_backup)

        info_panel, info_layout = make_panel("使用说明")
        info_layout.addWidget(help_label)
        layout.addWidget(info_panel)

        user_panel, user_layout = make_panel("安全与用户")
        user_service = UserService()
        can_manage_users = user_service.is_admin(current_user)
        user_label = QLabel(
            f"当前登录：{getattr(current_user, 'display_name', '本地用户')} "
            f"（{getattr(current_user, 'username', '未命名')}）"
        )
        user_label.setStyleSheet(
            "color: #425069; background: #f5f8fd; border: 1px solid #dce7f5; "
            "border-radius: 8px; padding: 10px 12px; font-weight: 700;"
        )
        user_layout.addWidget(user_label)
        user_actions = QHBoxLayout()
        change_password_button = make_button("修改我的账号")
        add_user_button = make_button("新增用户")
        user_actions.addWidget(change_password_button)
        user_actions.addWidget(add_user_button)
        user_actions.addStretch()
        user_layout.addLayout(user_actions)
        users_table = make_table(["用户名", "显示名称", "角色", "状态", "操作"], [])
        user_layout.addWidget(users_table)
        layout.addWidget(user_panel)

        def refresh_users():
            if not can_manage_users:
                return
            users = user_service.list_users(actor=current_user)
            users_table.setRowCount(len(users))
            users_table.setColumnCount(5)
            users_table.setHorizontalHeaderLabels(["用户名", "显示名称", "角色", "状态", "操作"])
            for row, user in enumerate(users):
                users_table.setItem(row, 0, QTableWidgetItem(user.username))
                users_table.setItem(row, 1, QTableWidgetItem(user.display_name))
                users_table.setItem(row, 2, QTableWidgetItem("系统管理员" if user.role == "admin" else "普通用户"))
                users_table.setItem(row, 3, QTableWidgetItem("启用" if user.is_active else "停用"))
                edit = make_button("编辑")
                edit.clicked.connect(lambda _checked=False, target=user: edit_user(target))
                users_table.setCellWidget(row, 4, edit)
                toggle = make_button("停用" if user.is_active else "启用")
                toggle.clicked.connect(
                    lambda _checked=False, user_id=user.id, active=user.is_active: toggle_user(user_id, active)
                )
                actions = QHBoxLayout()
                actions.setContentsMargins(4, 2, 4, 2)
                actions.setSpacing(4)
                actions.addWidget(edit)
                actions.addWidget(toggle)
                if user.id != getattr(current_user, "id", None):
                    remove = make_button("删除")
                    remove.clicked.connect(lambda _checked=False, target=user: delete_user(target))
                    actions.addWidget(remove)
                action_host = QLabel()
                action_host.setLayout(actions)
                users_table.setCellWidget(row, 4, action_host)
            users_table.resizeColumnsToContents()

        def toggle_user(user_id, active):
            try:
                user_service.set_active(user_id, not active, actor=current_user)
                refresh_users()
                show_toast(page, "用户状态已更新")
            except Exception as exc:
                show_toast(page, str(exc), False)

        if not can_manage_users:
            add_user_button.setVisible(False)
            users_table.setVisible(False)
            user_hint = QLabel("普通用户只能修改自己的账号，不能查看或管理其他用户。")
            user_hint.setStyleSheet("color: #627189; padding: 6px 0;")
            user_layout.addWidget(user_hint)

        def change_password():
            if not current_user:
                show_toast(page, "当前窗口没有登录用户信息", False)
                return
            old_edit = PasswordLineEdit()
            new_edit = PasswordLineEdit()
            confirm_edit = PasswordLineEdit()
            display_edit = QLineEdit(getattr(current_user, "display_name", ""))
            display_edit.setMaxLength(100)
            dialog = FormDialog(
                "修改我的账号", "显示名称可以直接修改；密码留空表示不修改密码。",
                [("显示名称", display_edit), ("原密码（改密码时填写）", old_edit),
                 ("新密码（可选）", new_edit), ("确认新密码", confirm_edit)],
                columns=1, field_width=330, width=520, height=470, parent=page,
            )
            dialog.save_button.setText("保存账号")

            def save_password():
                password_changed = bool(new_edit.text())
                if password_changed and not old_edit.text():
                    show_toast(dialog, "请输入原密码", False)
                    return
                if password_changed and len(new_edit.text()) < 6:
                    show_toast(dialog, "新密码至少需要 6 个字符", False)
                    return
                if new_edit.text() != confirm_edit.text():
                    show_toast(dialog, "两次输入的新密码不一致", False)
                    return
                try:
                    if new_edit.text():
                        user_service.change_password(
                            current_user.id, old_edit.text(), new_edit.text(), actor=current_user
                        )
                    user_service.update_user(
                        current_user.id,
                        actor=current_user,
                        display_name=display_edit.text(),
                    )
                    current_user.display_name = display_edit.text().strip() or current_user.username
                    dialog.accept()
                    if password_changed:
                        QMessageBox.information(page, "密码修改成功", "密码已修改，请使用新密码重新登录。")
                        if callable(on_password_changed):
                            on_password_changed()
                    else:
                        show_toast(page, "账号信息已修改")
                except Exception as exc:
                    show_toast(dialog, str(exc), False)

            dialog.save_button.clicked.connect(save_password)
            dialog.exec()

        def edit_user(target):
            username_edit = QLineEdit(target.username)
            display_edit = QLineEdit(target.display_name)
            role_box = QComboBox()
            role_box.addItem("普通用户", "user")
            role_box.addItem("系统管理员", "admin")
            role_box.setCurrentIndex(1 if target.role == "admin" else 0)
            active_box = QComboBox()
            active_box.addItem("启用", True)
            active_box.addItem("停用", False)
            active_box.setCurrentIndex(0 if target.is_active else 1)
            password_edit = PasswordLineEdit()
            fields = [
                ("用户名", username_edit), ("显示名称", display_edit),
                ("账户角色", role_box), ("状态", active_box),
                ("新密码（可选）", password_edit),
            ]
            dialog = FormDialog(
                "编辑用户", "管理员可以修改用户信息；新密码留空表示不修改密码。",
                fields, columns=1, field_width=330, width=560, height=500, parent=page,
            )
            dialog.save_button.setText("保存用户")

            def save_user():
                try:
                    user_service.update_user(
                        target.id,
                        actor=current_user,
                        username=username_edit.text(),
                        display_name=display_edit.text(),
                        role=role_box.currentData(),
                        is_active=active_box.currentData(),
                        new_password=password_edit.text() or None,
                    )
                    dialog.accept()
                    refresh_users()
                    show_toast(page, "用户信息已更新")
                except Exception as exc:
                    show_toast(dialog, str(exc), False)

            dialog.save_button.clicked.connect(save_user)
            dialog.exec()

        def delete_user(target):
            if not confirm_action(page, "确认删除用户", f"确定删除用户“{target.username}”吗？"):
                return
            try:
                user_service.delete_user(target.id, actor=current_user)
                refresh_users()
                show_toast(page, "用户已删除")
            except Exception as exc:
                show_toast(page, str(exc), False)

        def add_user():
            username_edit = QLineEdit()
            display_edit = QLineEdit()
            password_edit = PasswordLineEdit()
            confirm_edit = PasswordLineEdit()
            role_box = QComboBox()
            role_box.addItem("普通用户", "user")
            role_box.addItem("系统管理员", "admin")
            dialog = FormDialog(
                "新增用户", "创建后即可登录；请选择该账户的访问角色。",
                [("用户名", username_edit), ("显示名称", display_edit),
                 ("密码", password_edit), ("确认密码", confirm_edit),
                 ("账户角色", role_box)],
                columns=1, field_width=330, width=560, height=450, parent=page,
            )
            dialog.save_button.setText("创建用户")

            def save_user():
                if password_edit.text() != confirm_edit.text():
                    show_toast(dialog, "两次输入的密码不一致", False)
                    return
                try:
                    user_service.create_user(
                        username_edit.text(), password_edit.text(), display_edit.text(),
                        role=role_box.currentData() or "user",
                        actor=current_user,
                    )
                    dialog.accept()
                    refresh_users()
                    show_toast(page, "用户已创建")
                except Exception as exc:
                    show_toast(dialog, str(exc), False)

            dialog.save_button.clicked.connect(save_user)
            dialog.exec()

        change_password_button.clicked.connect(change_password)
        add_user_button.clicked.connect(add_user)
        refresh_users()
        return page
