from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QLineEdit, QComboBox, QSpinBox
from src.services.backup_service import BackupService
from src.ui.widgets.common import make_button, make_compact_form, make_page, make_panel, make_table, show_toast, confirm_action

class SettingsPage:
    def __new__(cls):
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
        panel_layout.addLayout(make_compact_form([
            ("备份目录（空=数据库目录）", data_dir_edit), ("自动备份", backup),
            ("备份文件格式", backup_format), ("密码导出", password),
            ("保留备份数量", retention),
        ], columns=2, field_width=380))
        panel_layout.addWidget(choose_dir_button)
        panel_layout.addWidget(last_backup)
        layout.addWidget(panel)

        roadmap_panel, roadmap_layout = make_panel("后续扩展")
        roadmap_layout.addWidget(make_table(
            ["功能", "说明", "阶段"],
            [
                ["SSH 自动采集", "自动采集系统、GPU、互联方式和网卡，并先选择所属项目", "已实现"],
                ["导入合并", "Excel 多 Sheet 识别、自动建项目、按 IP 合并机器", "已实现"],
                ["数据导出", "按项目选择导出项目、机器、SOP问题和费用", "已实现"],
                ["项目完整度检查", "检查项目基本信息、机器、SOP问题记录和费用", "已实现"],
                ["数据列表分页", "项目、机器、SOP记录、费用和导入记录按页加载", "已实现"],
                ["跨平台免安装打包", "Windows x64、macOS Intel、macOS ARM64 自动构建", "工作流已配置，待 CI 验证"],
            ],
        ))
        layout.addWidget(roadmap_panel)

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
        return page
