from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QComboBox, QFileDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from src.services.expense_service import ExpenseService
from src.services.project_service import ProjectService
from src.ui.widgets.common import (
    ClickableDateEdit,
    FormDialog,
    add_table_actions,
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
from src.utils.validators import EXPENSE_FIELD_LIMITS


class ExpensePage(QWidget):
    def __init__(self):
        super().__init__()
        self.project_service = ProjectService()
        self.expense_service = ExpenseService()
        self.build_ui()

    def build_ui(self):
        page, layout, _head = make_page("出差费用", "按项目维护交通、住宿、餐费等费用记录和报销状态。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        summary_panel, self.summary_layout = make_panel("费用概览")
        layout.addWidget(summary_panel)

        panel, panel_layout = make_panel("费用列表")
        toolbar, self.search_edit, refresh_btn, edit_btn, delete_btn, add_btn = make_management_toolbar("添加费用")
        self.project_filter = make_searchable_combo(QComboBox())
        self.project_filter.setMinimumWidth(340)
        self.project_filter.setMaximumWidth(460)
        filter_label = QLabel("项目筛选：")
        filter_label.setStyleSheet("font-weight: 700; color: #425069;")
        toolbar.insertWidget(1, filter_label)
        toolbar.insertWidget(2, self.project_filter)
        export_btn = make_button("导出 Excel")
        toolbar.insertWidget(4, export_btn)
        refresh_btn.clicked.connect(self.reload_data)
        edit_btn.clicked.connect(self.edit_selected_expense)
        delete_btn.clicked.connect(self.delete_selected_expense)
        add_btn.clicked.connect(lambda: self.open_expense_dialog())
        delete_all_btn = make_button("一键删除全部")
        delete_all_btn.setToolTip("删除全部费用记录")
        delete_all_btn.clicked.connect(self.delete_all_expenses)
        toolbar.insertWidget(toolbar.count() - 1, delete_all_btn)
        export_btn.clicked.connect(self.export_expenses)
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
        self.project_filter.addItem("全部项目", None)
        for project in self.project_service.get_all_projects():
            self.project_filter.addItem(display_project_name(project.name), project.id)
        index = self.project_filter.findData(selected_id)
        if index >= 0:
            self.project_filter.setCurrentIndex(index)
        self.project_filter.blockSignals(False)

    def reload_data(self):
        self.refresh_projects()
        self.refresh_table()

    def select_project(self, project_id):
        self.refresh_projects()
        index = self.project_filter.findData(project_id)
        if index >= 0:
            self.project_filter.setCurrentIndex(index)
        self.refresh_table()

    def refresh_table(self):
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if hasattr(self, "expense_table"):
            self.list_layout.removeWidget(self.expense_table)
            self.expense_table.deleteLater()
        project_id = self.project_filter.currentData()
        total_count, expenses = self.expense_service.get_expenses_page(self.pagination.page, self.pagination.page_size, project_id)
        self.pagination.set_total(total_count)
        total = self.expense_service.get_total_amount(project_id)
        project_labels = {p.id: display_project_name(p.name) for p in self.project_service.get_all_projects()}
        reimbursed = sum(float(item.amount) for item in expenses if item.is_reimbursed == "已报销")
        self.summary_layout.addWidget(make_table(
            ["项目", "费用合计", "已报销", "记录数"],
            [[self.project_filter.currentText() or "-", f"{float(total):.2f}", f"{reimbursed:.2f}", len(expenses)]],
        ))
        rows = [[
            expense.id, "", project_labels.get(expense.project_id, "-"), expense.expense_date, expense.expense_type, f"{float(expense.amount):.2f}",
            expense.remarks, expense.is_reimbursed,
        ] for expense in expenses]
        self.expense_table = make_table(["ID", "操作", "所属项目", "日期", "类型", "金额", "备注", "报销状态"], rows)
        self.expense_table.setColumnHidden(0, True)
        add_table_actions(
            self.expense_table, [expense.id for expense in expenses], self.edit_expense, self.delete_expense
        )
        self.expense_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_expense())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.expense_table, 1)
        self.apply_filter()

    def apply_filter(self):
        filter_table(self.expense_table, self.search_edit.text())

    def _selected_expense_id(self):
        row = self.expense_table.currentRow()
        item = self.expense_table.item(row, 0) if row >= 0 else None
        return int(item.text()) if item else None

    def open_expense_dialog(self, expense=None):
        project_box = make_searchable_combo(QComboBox())
        for project in self.project_service.get_all_projects():
            project_box.addItem(display_project_name(project.name), project.id)
        selected_project = expense.project_id if expense else self.project_filter.currentData()
        index = project_box.findData(selected_project)
        if index >= 0:
            project_box.setCurrentIndex(index)
        date_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        if expense:
            date_edit.setDate(expense.expense_date)
        type_box = QComboBox()
        type_box.setFocusPolicy(Qt.NoFocus)
        type_box.addItems(["交通", "住宿", "餐费", "打车", "其他"])
        type_box.setCurrentText(expense.expense_type if expense else "交通")
        amount_edit = QLineEdit(f"{float(expense.amount):.2f}" if expense else "0")
        amount_edit.setValidator(QDoubleValidator(0.0, 99999999.99, 2, self))
        amount_edit.setMaxLength(16)
        remark_edit = QLineEdit((expense.remarks or "") if expense else "")
        remark_edit.setMaxLength(EXPENSE_FIELD_LIMITS["remarks"])
        reimburse_box = QComboBox()
        reimburse_box.setFocusPolicy(Qt.NoFocus)
        reimburse_box.addItems(["未提交", "已提交", "已报销"])
        reimburse_box.setCurrentText((expense.is_reimbursed or "未提交") if expense else "未提交")
        dialog = FormDialog(
            "编辑费用" if expense else "添加费用",
            "金额最多保留两位小数，保存后项目汇总会立即更新。",
            [
                ("项目 *", project_box), ("日期 *", date_edit),
                ("费用类型 *", type_box), ("金额 *", amount_edit),
                ("备注", remark_edit), ("报销状态", reimburse_box),
            ],
            columns=2, field_width=330, width=820, height=460, parent=self,
        )

        def save():
            payload = {
                "project_id": project_box.currentData(),
                "expense_date": date_edit.date().toPython(),
                "expense_type": type_box.currentText(),
                "amount": amount_edit.text().strip(),
                "remarks": remark_edit.text().strip(),
                "is_reimbursed": reimburse_box.currentText(),
            }
            try:
                if expense:
                    self.expense_service.update_expense(expense.id, **payload)
                else:
                    self.expense_service.create_expense(**payload)
                dialog.accept()
                self.select_project(project_box.currentData())
                show_toast(self, "费用已更新" if expense else "费用已添加")
            except Exception as exc:
                show_toast(dialog, str(exc), False)

        dialog.save_button.setText("更新" if expense else "添加")
        dialog.save_button.clicked.connect(save)
        dialog.exec()

    def edit_selected_expense(self):
        expense_id = self._selected_expense_id()
        if not expense_id:
            show_toast(self, "请先选择需要编辑的费用", False)
            return
        self.edit_expense(expense_id)

    def edit_expense(self, expense_id):
        expense = self.expense_service.get_expense_by_id(expense_id)
        if expense:
            self.open_expense_dialog(expense)

    def delete_selected_expense(self):
        expense_ids = selected_record_ids(self.expense_table)
        if not expense_ids:
            show_toast(self, "请先选择需要删除的费用", False)
            return
        if len(expense_ids) == 1:
            self.delete_expense(expense_ids[0])
            return
        if confirm_action(self, "确认批量删除", f"确定删除选中的 {len(expense_ids)} 条费用记录吗？"):
            for expense_id in expense_ids:
                self.expense_service.delete_expense(expense_id)
            self.refresh_table()
            show_toast(self, f"已删除 {len(expense_ids)} 条费用记录")

    def delete_expense(self, expense_id):
        if confirm_action(self, "确认删除", "确定删除选中的费用记录吗？"):
            self.expense_service.delete_expense(expense_id)
            self.refresh_table()
            show_toast(self, "费用已删除")

    def delete_all_expenses(self):
        total, _ = self.expense_service.get_expenses_page(1, 1)
        if total and confirm_action(self, "确认删除全部费用", f"确定删除全部 {total} 条费用记录吗？此操作不可恢复。"):
            removed = self.expense_service.delete_all_expenses()
            self.pagination.page = 1
            self.refresh_table()
            show_toast(self, f"已删除全部费用，共 {removed} 条")

    def export_expenses(self):
        project_id = self.project_filter.currentData()
        if not project_id:
            show_toast(self, "请先选择项目", False)
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出费用明细", f"{self.project_filter.currentText()}_出差费用.xlsx", "Excel (*.xlsx)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"
        try:
            self.expense_service.export_expenses(project_id, file_path)
            show_toast(self, f"费用明细已导出到：{file_path}")
        except Exception as exc:
            show_toast(self, f"导出失败：{exc}", False)
