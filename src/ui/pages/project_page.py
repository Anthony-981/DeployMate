from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QVBoxLayout, QWidget, QDialog, QLabel

from src.services.project_service import ProjectService
from src.services.user_service import UserService
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
    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.service = ProjectService(current_user)
        self.user_service = UserService()
        self.is_admin = self.user_service.is_admin(current_user)
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
        if self.is_admin:
            self.user_filter = QComboBox()
            self.user_filter.setMinimumWidth(240)
            self.user_filter.currentIndexChanged.connect(self.apply_filter)
            toolbar.insertWidget(1, QLabel("用户筛选："))
            toolbar.insertWidget(2, self.user_filter)
            self.refresh_users()
        refresh_btn.clicked.connect(self.refresh_table)
        edit_btn.clicked.connect(self.edit_selected_project)
        delete_btn.clicked.connect(self.delete_selected_project)
        add_btn.clicked.connect(lambda: self.open_project_dialog())
        delete_all_btn = make_button("一键删除全部")
        delete_all_btn.setToolTip("删除全部项目及其关联数据")
        delete_all_btn.clicked.connect(self.delete_all_projects)
        toolbar.insertWidget(toolbar.count() - 1, delete_all_btn)
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
        owner_id = self.user_filter.currentData() if self.is_admin else None
        total, projects = self.service.get_projects_page(
            self.pagination.page, self.pagination.page_size, self.search_edit.text(), owner_id
        )
        if self.pagination.set_total(total):
            total, projects = self.service.get_projects_page(
                self.pagination.page, self.pagination.page_size, self.search_edit.text(), owner_id
            )
        owner_labels = self.user_service.get_user_label_map(
            [project.owner_id for project in projects if project.owner_id], actor=self.current_user
        ) if self.is_admin else {}
        rows = []
        for project in projects:
            row = [
                project.id, "", display_project_name(project.name), project.sales,
                project.project_code, project.location, project.start_date, project.end_date, project.status,
            ]
            if self.is_admin:
                row.insert(2, owner_labels.get(project.owner_id, "未分配用户"))
            rows.append(row)
        headers = ["编号", "操作", "项目客户名称", "销售", "订单编号", "地点", "开始日期", "结束日期", "状态"]
        if self.is_admin:
            headers.insert(2, "所属用户")
        self.project_table = make_table(
            headers, rows
        )
        self.project_table.setColumnHidden(0, True)
        add_table_actions(
            self.project_table, [project.id for project in projects], self.edit_project, self.delete_project
        )
        self.project_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_project())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.project_table, 1)
    def reload_data(self):
        self.pagination.reset()
        if self.is_admin:
            self.refresh_users()
        self.refresh_table()

    def apply_filter(self):
        self.pagination.reset()
        self.refresh_table()

    def refresh_users(self):
        self.user_filter.blockSignals(True)
        selected = self.user_filter.currentData()
        self.user_filter.clear()
        self.user_filter.addItem("全部用户", None)
        for user_id, label in self.user_service.get_user_options(actor=self.current_user):
            self.user_filter.addItem(label, user_id)
        index = self.user_filter.findData(selected)
        if index >= 0:
            self.user_filter.setCurrentIndex(index)
        self.user_filter.blockSignals(False)

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
            self, "确认批量删除", f"确定删除选中的 {len(project_ids)} 个项目吗？\n仅删除关联机器，其他资料保留。"
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
            self, "确认删除", f"确定删除项目“{project.name}”吗？\n仅删除关联机器，SOP、费用和导入记录保留。"
        ):
            self.service.delete_project(project_id)
            self.refresh_table()
            show_toast(self, "项目已删除")

    def delete_all_projects(self):
        total = self.service.get_project_stats()["total"]
        if not total:
            show_toast(self, "当前没有项目可删除")
            return
        if confirm_action(self, "确认删除全部项目", f"确定删除全部 {total} 个项目吗？仅删除机器，其他资料保留。"):
            removed = self.service.delete_all_projects()
            self.pagination.page = 1
            self.refresh_table()
            show_toast(self, f"已删除全部项目，共 {removed} 个")
