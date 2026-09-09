from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QVBoxLayout, QWidget, QDialog, QLabel

from src.services.project_service import ProjectService
from src.ui.widgets.common import (
    ClickableDateEdit,
    FormDialog,
    add_table_actions,
    confirm_action,
    configure_date_edit,
    filter_table,
    make_management_toolbar,
    make_button,
    make_page,
    make_panel,
    make_table,
    show_toast,
    selected_record_ids,
    PaginationBar,
    display_project_name,
)
from src.utils.validators import PROJECT_FIELD_LIMITS


class ProjectPage(QWidget):
    def __init__(self):
        super().__init__()
        self.service = ProjectService()
        self.build_ui()

    def build_ui(self):
        page, layout, head = make_page("项目管理", "统一维护项目资料，并关联机器、SOP记录、费用和导出数据。")
        completeness_btn = make_button("检查项目完整度")
        completeness_btn.clicked.connect(self.show_completeness)
        head.addWidget(completeness_btn)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        panel, panel_layout = make_panel("项目列表")
        toolbar, self.search_edit, refresh_btn, edit_btn, delete_btn, add_btn = make_management_toolbar("添加项目")
        refresh_btn.clicked.connect(self.refresh_table)
        edit_btn.clicked.connect(self.edit_selected_project)
        delete_btn.clicked.connect(self.delete_selected_project)
        add_btn.clicked.connect(lambda: self.open_project_dialog())
        self.search_edit.textChanged.connect(self.apply_filter)
        panel_layout.addLayout(toolbar)
        layout.addWidget(panel)
        self.list_layout = panel_layout
        self.pagination = PaginationBar()
        self.pagination.page_changed.connect(lambda _page: self.refresh_table())
        panel_layout.addWidget(self.pagination)
        self.refresh_table()

    def refresh_table(self):
        if hasattr(self, "project_table"):
            self.list_layout.removeWidget(self.project_table)
            self.project_table.deleteLater()
        total, projects = self.service.get_projects_page(self.pagination.page, self.pagination.page_size)
        self.pagination.set_total(total)
        rows = [[
            project.id, "", display_project_name(project.name), project.sales, project.project_code, project.location,
            project.start_date, project.end_date, project.status,
        ] for project in projects]
        self.project_table = make_table(
            ["ID", "操作", "项目客户名称", "销售", "订单编号", "地点", "开始日期", "结束日期", "状态"], rows
        )
        self.project_table.setColumnHidden(0, True)
        add_table_actions(
            self.project_table, [project.id for project in projects], self.edit_project, self.delete_project
        )
        self.project_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_project())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.project_table, 1)
        self.apply_filter()

    def reload_data(self):
        self.refresh_table()

    def apply_filter(self):
        filter_table(self.project_table, self.search_edit.text())

    def show_completeness(self):
        result = self.service.get_completeness()
        dialog = QDialog(self)
        dialog.setWindowTitle("项目完整度检查")
        dialog.resize(860, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"整体完整度：{result['average']}%    共检查 {len(result['projects'])} 个项目"))
        rows = [[item["name"], f"{item['score']}%", "、".join(item["missing"]) or "完整"] for item in result["projects"]]
        layout.addWidget(make_table(["项目", "完整度", "缺失项"], rows or [["暂无项目", "0%", "-"]]))
        close_button = make_button("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def _selected_project_id(self):
        row = self.project_table.currentRow()
        item = self.project_table.item(row, 0) if row >= 0 else None
        return int(item.text()) if item else None

    def open_project_dialog(self, project=None):
        name_edit = QLineEdit(project.name if project else "")
        code_edit = QLineEdit((project.project_code or "") if project else "")
        location_edit = QLineEdit((project.location or "") if project else "")
        start_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        end_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        if project and project.start_date:
            start_edit.setDate(project.start_date)
        if project and project.end_date:
            end_edit.setDate(project.end_date)
        sales_edit = QLineEdit((project.sales or "") if project else "")
        status_box = QComboBox()
        status_box.setFocusPolicy(Qt.NoFocus)
        status_box.addItems(["待开始", "实施中", "已完成", "已归档"])
        status_box.setCurrentText((project.status or "待开始") if project else "待开始")

        for edit, limit in (
            (name_edit, PROJECT_FIELD_LIMITS["name"]),
            (code_edit, PROJECT_FIELD_LIMITS["project_code"]),
            (location_edit, PROJECT_FIELD_LIMITS["location"]),
            (sales_edit, PROJECT_FIELD_LIMITS["sales"]),
        ):
            edit.setMaxLength(limit)

        dialog = FormDialog(
            "编辑项目" if project else "添加项目",
            "项目客户名称为必填项，订单编号可后续补充。",
            [
                ("项目客户名称 *", name_edit), ("销售", sales_edit),
                ("订单编号", code_edit), ("实施地点", location_edit),
                ("开始日期", start_edit), ("结束日期", end_edit),
                ("项目状态", status_box),
            ],
            columns=4,
            field_width=220,
            width=1200,
            height=390,
            parent=self,
        )

        def save():
            payload = {
                "name": name_edit.text().strip(),
                "project_code": code_edit.text().strip(),
                "location": location_edit.text().strip(),
                "start_date": start_edit.date().toPython(),
                "end_date": end_edit.date().toPython(),
                "sales": sales_edit.text().strip(),
                "status": status_box.currentText(),
            }
            try:
                if project:
                    self.service.update_project(project.id, **payload)
                else:
                    self.service.create_project(**payload)
                dialog.accept()
                self.refresh_table()
                show_toast(self, "项目已更新" if project else "项目已添加")
            except Exception as exc:
                show_toast(dialog, str(exc), False)

        dialog.save_button.setText("更新" if project else "添加")
        dialog.save_button.clicked.connect(save)
        dialog.exec()

    def edit_selected_project(self):
        project_id = self._selected_project_id()
        if not project_id:
            show_toast(self, "请先选择需要编辑的项目", False)
            return
        self.edit_project(project_id)

    def edit_project(self, project_id):
        project = self.service.get_project_by_id(project_id)
        if project:
            self.open_project_dialog(project)

    def delete_selected_project(self):
        project_ids = selected_record_ids(self.project_table)
        if not project_ids:
            show_toast(self, "请先选择需要删除的项目", False)
            return
        if len(project_ids) == 1:
            self.delete_project(project_ids[0])
            return
        if confirm_action(
            self, "确认批量删除", f"确定删除选中的 {len(project_ids)} 个项目吗？\n关联数据也会一并删除。"
        ):
            for project_id in project_ids:
                self.service.delete_project(project_id)
            self.refresh_table()
            show_toast(self, f"已删除 {len(project_ids)} 个项目")

    def delete_project(self, project_id):
        project = self.service.get_project_by_id(project_id)
        if not project:
            self.refresh_table()
            return
        if confirm_action(
            self, "确认删除", f"确定删除项目“{project.name}”吗？\n关联的机器、SOP记录、费用和导入记录也会删除。"
        ):
            self.service.delete_project(project_id)
            self.refresh_table()
            show_toast(self, "项目已删除")
