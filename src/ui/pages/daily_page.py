from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QLabel, QVBoxLayout, QWidget

from src.services.daily_report_service import DailyReportService
from src.services.project_service import ProjectService
from src.ui.widgets.common import (
    ClickableDateEdit,
    FormDialog,
    add_table_actions,
    LimitedTextEdit,
    configure_date_edit,
    confirm_action,
    filter_table,
    make_button,
    make_management_toolbar,
    make_page,
    make_panel,
    make_table,
    show_toast,
    selected_record_ids,
    make_searchable_combo,
    PaginationBar,
    display_project_name,
)
from src.utils.validators import DAILY_FIELD_LIMITS


class DailyPage(QWidget):
    def __init__(self):
        super().__init__()
        self.project_service = ProjectService()
        self.report_service = DailyReportService()
        self.build_ui()

    def build_ui(self):
        page, layout, _head = make_page("SOP问题记录", "记录实施过程中遇到的问题、解决方法和后续建议，可导出 Word 或 Markdown。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        panel, panel_layout = make_panel("SOP问题列表")
        toolbar, self.search_edit, refresh_btn, edit_btn, delete_btn, add_btn = make_management_toolbar("添加SOP问题")
        self.project_filter = make_searchable_combo(QComboBox())
        self.project_filter.setMinimumWidth(340)
        self.project_filter.setMaximumWidth(460)
        filter_label = QLabel("项目筛选：")
        filter_label.setStyleSheet("font-weight: 700; color: #425069;")
        toolbar.insertWidget(1, filter_label)
        toolbar.insertWidget(2, self.project_filter)
        word_btn = make_button("导出 Word")
        markdown_btn = make_button("导出 Markdown")
        toolbar.insertWidget(4, word_btn)
        toolbar.insertWidget(5, markdown_btn)
        refresh_btn.clicked.connect(self.reload_data)
        edit_btn.clicked.connect(self.edit_selected_report)
        delete_btn.clicked.connect(self.delete_selected_report)
        add_btn.clicked.connect(lambda: self.open_report_dialog())
        delete_all_btn = make_button("一键删除全部")
        delete_all_btn.setToolTip("删除全部 SOP 记录")
        delete_all_btn.clicked.connect(self.delete_all_reports)
        toolbar.insertWidget(toolbar.count() - 1, delete_all_btn)
        word_btn.clicked.connect(lambda: self.export_reports("docx"))
        markdown_btn.clicked.connect(lambda: self.export_reports("md"))
        self.search_edit.textChanged.connect(self.apply_filter)
        self.project_filter.currentIndexChanged.connect(self.refresh_table)
        panel_layout.addLayout(toolbar)
        layout.addWidget(panel)
        self.list_layout = panel_layout
        self.pagination = PaginationBar()
        self.pagination.page_changed.connect(lambda _page: self.refresh_table())
        panel_layout.addWidget(self.pagination)
        self.refresh_projects()
        self.refresh_table()

    def refresh_projects(self):
        selected_id = self.project_filter.currentData()
        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        for project in self.project_service.get_all_projects():
            self.project_filter.addItem(display_project_name(project.name), project.id)
        index = self.project_filter.findData(selected_id)
        if index >= 0:
            self.project_filter.setCurrentIndex(index)
        self.project_filter.blockSignals(False)

    def reload_data(self):
        self.refresh_projects()
        self.refresh_table()

    def refresh_table(self):
        if hasattr(self, "report_table"):
            self.list_layout.removeWidget(self.report_table)
            self.report_table.deleteLater()
        project_id = self.project_filter.currentData()
        total, reports = self.report_service.get_reports_page(self.pagination.page, self.pagination.page_size, project_id)
        self.pagination.set_total(total)
        rows = [[
            report.id, "", report.report_date, report.work_content, report.problems,
            report.solutions, report.next_plan, report.status,
        ] for report in reports]
        self.report_table = make_table(
            ["ID", "操作", "日期", "SOP主题/步骤", "遇到的问题", "解决方法", "后续建议", "状态"], rows
        )
        self.report_table.setColumnHidden(0, True)
        add_table_actions(
            self.report_table, [report.id for report in reports], self.edit_report, self.delete_report
        )
        self.report_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_report())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.report_table, 1)
        self.apply_filter()

    def apply_filter(self):
        filter_table(self.report_table, self.search_edit.text())

    def _selected_report_id(self):
        row = self.report_table.currentRow()
        item = self.report_table.item(row, 0) if row >= 0 else None
        return int(item.text()) if item else None

    def open_report_dialog(self, report=None):
        project_box = make_searchable_combo(QComboBox())
        for project in self.project_service.get_all_projects():
            project_box.addItem(display_project_name(project.name), project.id)
        selected_project = report.project_id if report else self.project_filter.currentData()
        index = project_box.findData(selected_project)
        if index >= 0:
            project_box.setCurrentIndex(index)
        date_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        if report:
            date_edit.setDate(report.report_date)
        status_box = QComboBox()
        status_box.setFocusPolicy(Qt.NoFocus)
        status_box.addItems(["草稿", "已完成"])
        status_box.setCurrentText((report.status or "草稿") if report else "草稿")
        editors = {
            "problems": LimitedTextEdit(DAILY_FIELD_LIMITS["problems"]),
            "solutions": LimitedTextEdit(DAILY_FIELD_LIMITS["solutions"]),
            "next_plan": LimitedTextEdit(DAILY_FIELD_LIMITS["next_plan"]),
            "remarks": LimitedTextEdit(DAILY_FIELD_LIMITS["remarks"]),
        }
        for key, editor in editors.items():
            if report and key == "solutions":
                value = report.solutions or report.work_content or ""
            else:
                value = getattr(report, key, "") if report else ""
            editor.setPlainText(str(value or ""))
            editor.setMinimumHeight(76)
            editor.setMaximumHeight(100)
        dialog = FormDialog(
            "编辑SOP问题" if report else "添加SOP问题",
            "项目、遇到的问题、解决办法和步骤为必填项，同一项目每天保留一条记录。",
            [
                ("项目 *", project_box), ("日期 *", date_edit),
                ("遇到的问题 *", editors["problems"]), ("解决办法和步骤 *", editors["solutions"]),
                ("后续建议", editors["next_plan"]), ("备注", editors["remarks"]),
                ("状态", status_box),
            ],
            columns=2, field_width=420, width=980, height=650, parent=self,
        )

        def save():
            payload = {
                "project_id": project_box.currentData(),
                "report_date": date_edit.date().toPython(),
                "work_content": editors["solutions"].toPlainText().strip(),
                **{key: editor.toPlainText().strip() for key, editor in editors.items()},
                "status": status_box.currentText(),
            }
            try:
                if report:
                    self.report_service.update_report(report.id, **payload)
                else:
                    self.report_service.create_report(**payload)
                dialog.accept()
                self.select_project(project_box.currentData())
                show_toast(self, "SOP问题已更新" if report else "SOP问题已添加")
            except Exception as exc:
                show_toast(dialog, str(exc), False)

        dialog.save_button.setText("更新" if report else "添加")
        dialog.save_button.clicked.connect(save)
        dialog.exec()

    def select_project(self, project_id):
        self.refresh_projects()
        index = self.project_filter.findData(project_id)
        if index >= 0:
            self.project_filter.setCurrentIndex(index)
        self.refresh_table()

    def edit_selected_report(self):
        report_id = self._selected_report_id()
        if not report_id:
            show_toast(self, "请先选择需要编辑的SOP问题", False)
            return
        self.edit_report(report_id)

    def edit_report(self, report_id):
        report = self.report_service.get_report_by_id(report_id)
        if report:
            self.open_report_dialog(report)

    def delete_selected_report(self):
        report_ids = selected_record_ids(self.report_table)
        if not report_ids:
            show_toast(self, "请先选择需要删除的SOP问题", False)
            return
        if len(report_ids) == 1:
            self.delete_report(report_ids[0])
            return
        if confirm_action(self, "确认批量删除", f"确定删除选中的 {len(report_ids)} 条SOP记录吗？"):
            for report_id in report_ids:
                self.report_service.delete_report(report_id)
            self.refresh_table()
            show_toast(self, f"已删除 {len(report_ids)} 条SOP记录")

    def delete_report(self, report_id):
        if confirm_action(self, "确认删除", "确定删除选中的SOP问题吗？"):
            self.report_service.delete_report(report_id)
            self.refresh_table()
            show_toast(self, "SOP问题已删除")

    def delete_all_reports(self):
        total = self.report_service.get_report_count()
        if total and confirm_action(self, "确认删除全部SOP记录", f"确定删除全部 {total} 条SOP记录吗？此操作不可恢复。"):
            removed = self.report_service.delete_all_reports()
            self.pagination.page = 1
            self.refresh_table()
            show_toast(self, f"已删除全部SOP记录，共 {removed} 条")

    def export_reports(self, file_format: str):
        project_id = self.project_filter.currentData()
        if not project_id:
            show_toast(self, "请先选择项目", False)
            return
        suffix = ".docx" if file_format == "docx" else ".md"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出SOP问题", f"{self.project_filter.currentText()}_SOP问题记录{suffix}",
            f"{'Word' if file_format == 'docx' else 'Markdown'} (*{suffix})",
        )
        if not file_path:
            return
        try:
            self.report_service.export_reports(project_id, file_path, file_format)
            show_toast(self, f"SOP问题记录已导出到：{file_path}")
        except Exception as exc:
            show_toast(self, f"导出失败：{exc}", False)
