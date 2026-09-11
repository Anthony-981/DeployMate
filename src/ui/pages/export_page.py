from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLabel, QVBoxLayout, QWidget

from src.services.export_service import ExportService
from src.services.project_service import ProjectService
from src.ui.widgets.common import make_button, make_compact_form, make_page, make_panel, make_table, show_toast, make_searchable_combo, display_project_name


class ExportPage(QWidget):
    FORMAT_OPTIONS = {
        "Excel 工作簿": "xlsx",
        "Word 文档": "docx",
        "Markdown 文档": "md",
        "ZIP 项目资料包": "zip",
        "SQLite 数据库": "db",
    }

    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.project_service = ProjectService(current_user)
        self.export_service = ExportService(current_user)
        self.build_ui()

    def build_ui(self):
        page, layout, head = make_page("导出资料", "从本地数据库导出当前项目的项目、机器、SOP问题记录和费用数据。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        refresh_btn = make_button("刷新项目")
        refresh_btn.clicked.connect(self.refresh_projects)
        head.addWidget(refresh_btn)
        export_btn = make_button("一键导出", True)
        export_btn.clicked.connect(self.export_project)
        head.addWidget(export_btn)
        self.export_dir = ""
        choose_dir_btn = make_button("选择本地目录")
        choose_dir_btn.clicked.connect(self.choose_export_dir)
        head.addWidget(choose_dir_btn)

        panel, panel_layout = make_panel("导出设置")
        self.project_box = make_searchable_combo(QComboBox())
        self.project_box.setMinimumWidth(360)
        self.project_box.setMaximumWidth(480)
        self.format_box = QComboBox()
        self.format_box.setFocusPolicy(Qt.NoFocus)
        self.format_box.addItems(self.FORMAT_OPTIONS.keys())
        panel_layout.addLayout(make_compact_form([
            ("目标项目", self.project_box), ("导出格式", self.format_box),
        ], columns=2, field_width=360))
        layout.addWidget(panel)

        content_panel, content_layout = make_panel("包含内容")
        self.project_check = QCheckBox("项目基本信息")
        self.machine_check = QCheckBox("机器信息（包含密码）")
        self.report_check = QCheckBox("SOP问题记录")
        self.expense_check = QCheckBox("出差费用")
        for check in (self.project_check, self.machine_check, self.report_check, self.expense_check):
            check.setChecked(True)
        content_layout.addWidget(self.project_check)
        content_layout.addWidget(self.machine_check)
        content_layout.addWidget(self.report_check)
        content_layout.addWidget(self.expense_check)
        content_layout.addWidget(make_table(
            ["数据类型", "导出内容", "说明"],
            [
                ["项目基本信息", "名称、客户、编号、地点、销售、状态", "自动包含"],
                ["机器信息", "网络、账号、硬件、GPU、系统信息", "默认包含密码，可取消"],
                ["SOP问题记录", "SOP主题、遇到的问题、解决方法、后续建议", "自动包含"],
                ["出差费用", "费用日期、出差人员、出差起止日期、分类、金额、报销状态", "自动包含"],
            ],
        ))
        layout.addWidget(content_panel)
        self.status_label = QLabel("请选择项目和格式后开始导出。")
        self.status_label.setStyleSheet("color: #627189; font-size: 14px;")
        layout.addWidget(self.status_label)
        self.refresh_projects()

    def choose_export_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if directory:
            self.export_dir = directory
            self.status_label.setText(f"导出目录：{directory}")

    def refresh_projects(self):
        selected = self.project_box.currentData()
        self.project_box.clear()
        self.project_box.addItem("全部项目", None)
        for project_id, project_name in self.project_service.get_project_options():
            self.project_box.addItem(display_project_name(project_name), project_id)
        index = self.project_box.findData(selected)
        if index >= 0:
            self.project_box.setCurrentIndex(index)

    def reload_data(self):
        self.refresh_projects()

    def export_project(self):
        project_id = self.project_box.currentData()
        project_ids = [project_id] if project_id else None
        file_format = self.FORMAT_OPTIONS[self.format_box.currentText()]
        checks = (self.project_check, self.machine_check, self.report_check, self.expense_check)
        if file_format != "db" and not any(check.isChecked() for check in checks):
            show_toast(self, "请至少选择一类导出内容", False)
            return
        suffix = f".{file_format}"
        project_name = self.project_box.currentText().split(" / ", 1)[0]
        filters = {
            "xlsx": "Excel (*.xlsx)", "docx": "Word (*.docx)", "md": "Markdown (*.md)",
            "zip": "ZIP (*.zip)", "db": "SQLite (*.db)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出项目资料", str(Path(self.export_dir or ".") / f"{project_name}_项目资料{suffix}"), filters[file_format]
        )
        if not file_path:
            return
        if not file_path.lower().endswith(suffix):
            file_path += suffix
        try:
            if file_format == "db":
                self.export_service.export_database(file_path)
            else:
                self.export_service.export_projects(
                    project_ids, file_path, file_format,
                    include_projects=self.project_check.isChecked(),
                    include_machines=self.machine_check.isChecked(),
                    include_reports=self.report_check.isChecked(),
                    include_expenses=self.expense_check.isChecked(),
                    include_passwords=self.machine_check.isChecked(),
                )
            self.status_label.setText(f"最近导出：{Path(file_path).name} -> {file_path}")
            show_toast(self, f"项目资料已导出到：{file_path}")
        except Exception as exc:
            show_toast(self, f"导出失败：{exc}", False)
