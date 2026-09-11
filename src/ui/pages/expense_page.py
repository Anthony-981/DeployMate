from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QComboBox, QFileDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from src.services.expense_service import ExpenseService
from src.services.project_service import ProjectService
from src.services.user_service import UserService
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
    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.project_service = ProjectService(current_user)
        self.expense_service = ExpenseService(current_user)
        self.user_service = UserService()
        self.is_admin = self.user_service.is_admin(current_user)
        self.build_ui()

    def build_ui(self):
        page, layout, _head = make_page("费用与利润", "分别记录考核费用和出差费用，自动计算实际利润。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        summary_panel, self.summary_layout = make_panel("费用概览")
        self.formula_label = QLabel("计算公式：实际利润 = 考核费用 - 出差费用")
        self.formula_label.setObjectName("profitFormulaLabel")
        self.formula_label.setStyleSheet(
            "color: #315d9a; background: #edf4ff; border: 1px solid #d7e6ff;"
            " border-radius: 6px; padding: 8px 12px; font-weight: 700;"
        )
        layout.addWidget(summary_panel)

        panel, panel_layout = make_panel("费用列表")
        toolbar, self.search_edit, refresh_btn, edit_btn, delete_btn, add_btn = make_management_toolbar("添加费用")
        if self.is_admin:
            self.user_filter = make_searchable_combo(QComboBox())
            self.user_filter.setMinimumWidth(260)
            self.user_filter.setMaximumWidth(360)
            user_label = QLabel("用户筛选：")
            user_label.setStyleSheet("font-weight: 700; color: #425069;")
            toolbar.insertWidget(1, user_label)
            toolbar.insertWidget(2, self.user_filter)
        self.project_filter = make_searchable_combo(QComboBox())
        self.project_filter.setMinimumWidth(340)
        self.project_filter.setMaximumWidth(460)
        filter_label = QLabel("项目筛选：")
        filter_label.setStyleSheet("font-weight: 700; color: #425069;")
        insert_at = 3 if self.is_admin else 1
        toolbar.insertWidget(insert_at, filter_label)
        toolbar.insertWidget(insert_at + 1, self.project_filter)
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
        self.search_edit.textChanged.connect(self._search_changed)
        if self.is_admin:
            self.user_filter.currentIndexChanged.connect(self._user_scope_changed)
        self.project_filter.currentIndexChanged.connect(self._reset_and_refresh)
        panel_layout.addLayout(toolbar)
        layout.addWidget(panel)
        self.list_layout = panel_layout
        self.pagination = PaginationBar()
        self.pagination.page_changed.connect(lambda _page: self.refresh_table())
        panel_layout.addWidget(self.pagination)
        if self.is_admin:
            self.refresh_users()
        self.refresh_projects()
        self.refresh_table()

    def refresh_users(self):
        self.user_filter.blockSignals(True)
        selected_id = self.user_filter.currentData()
        self.user_filter.clear()
        self.user_filter.addItem("全部用户", None)
        for user_id, label in self.user_service.get_user_options(actor=self.current_user):
            self.user_filter.addItem(label, user_id)
        index = self.user_filter.findData(selected_id)
        if index >= 0:
            self.user_filter.setCurrentIndex(index)
        self.user_filter.blockSignals(False)

    def _selected_owner_id(self):
        return self.user_filter.currentData() if self.is_admin else None

    def _user_scope_changed(self):
        self.pagination.reset()
        self.refresh_projects()
        self.refresh_table()

    def refresh_projects(self):
        selected_id = self.project_filter.currentData()
        self.project_filter.blockSignals(True)
        self.project_filter.clear()
        self.project_filter.addItem("全部项目", None)
        for project_id, project_name in self.project_service.get_project_options(self._selected_owner_id()):
            self.project_filter.addItem(display_project_name(project_name), project_id)
        index = self.project_filter.findData(selected_id)
        if index >= 0:
            self.project_filter.setCurrentIndex(index)
        self.project_filter.blockSignals(False)

    def reload_data(self):
        self.pagination.reset()
        if self.is_admin:
            self.refresh_users()
        self.refresh_projects()
        self.refresh_table()

    def _reset_and_refresh(self):
        self.pagination.reset()
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
            if item.widget() and item.widget() is not self.formula_label:
                item.widget().deleteLater()
        if hasattr(self, "expense_table"):
            self.list_layout.removeWidget(self.expense_table)
            self.expense_table.deleteLater()
        project_id = self.project_filter.currentData()
        total_count, expenses = self.expense_service.get_expenses_page(
            self.pagination.page, self.pagination.page_size, project_id,
            self.search_edit.text(), self._selected_owner_id()
        )
        if self.pagination.set_total(total_count):
            total_count, expenses = self.expense_service.get_expenses_page(
                self.pagination.page, self.pagination.page_size, project_id,
                self.search_edit.text(), self._selected_owner_id()
            )
        summaries = self.expense_service.get_profit_summaries_by_project(
            project_id, self.search_edit.text(), self._selected_owner_id()
        )
        self.summary_layout.addWidget(self.formula_label)
        summary_owner_labels = self.user_service.get_user_label_map(
            [summary["owner_id"] for summary in summaries if summary.get("owner_id")],
            actor=self.current_user,
        ) if self.is_admin else {}
        summary_rows = []
        for summary in summaries:
            row = [
                display_project_name(summary["project_name"]),
                f"{summary['assessment_fee']:.2f}",
                f"{summary['actual_cost']:.2f}",
                f"{summary['profit']:.2f}",
                summary["count"],
            ]
            if self.is_admin:
                row.insert(0, summary_owner_labels.get(summary.get("owner_id"), "未分配用户"))
            summary_rows.append(row)
        summary_headers = ["项目", "总考核费用", "总出差费用", "实际利润", "记录数"]
        if self.is_admin:
            summary_headers.insert(0, "所属用户")
        self.summary_table = make_table(
            summary_headers,
            summary_rows,
        )
        self.summary_table.setObjectName("expenseSummaryTable")
        self.summary_layout.addWidget(self.summary_table)
        rows = []
        owner_labels = self.user_service.get_user_label_map(
            [expense.owner_id for expense, _project_name in expenses if expense.owner_id],
            actor=self.current_user,
        ) if self.is_admin else {}
        for expense, project_name in expenses:
            breakdown = self.expense_service.amount_breakdown(expense)
            row = [
                expense.id, "", display_project_name(project_name or "未关联项目"),
                expense.travel_person or "-",
                expense.travel_start_date or "-",
                expense.travel_end_date or "-",
                expense.expense_date,
                f"{breakdown['assessment_fee'] + breakdown['actual_cost']:.2f}",
                f"{breakdown['assessment_fee']:.2f}",
                f"{breakdown['actual_cost']:.2f}",
                f"{breakdown['profit']:.2f}",
                expense.remarks,
                expense.is_reimbursed,
            ]
            if self.is_admin:
                row.insert(2, owner_labels.get(expense.owner_id, "未分配用户"))
            rows.append(row)
        headers = [
            "编号", "操作", "所属项目", "出差人员", "出差开始",
            "出差结束", "费用日期", "费用合计",
            "考核费用", "出差费用", "本条利润", "备注", "报销状态",
        ]
        if self.is_admin:
            headers.insert(2, "所属用户")
        self.expense_table = make_table(
            headers,
            rows,
        )
        self.expense_table.setColumnHidden(0, True)
        add_table_actions(
            self.expense_table, [expense.id for expense, _project_name in expenses], self.edit_expense, self.delete_expense
        )
        self.expense_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_expense())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.expense_table, 1)
    def apply_filter(self):
        self._search_changed()

    def _search_changed(self):
        self.pagination.reset()
        self.refresh_table()

    def _selected_expense_id(self):
        row = self.expense_table.currentRow()
        item = self.expense_table.item(row, 0) if row >= 0 else None
        return int(item.text()) if item else None

    def open_expense_dialog(self, expense=None):
        project_box = make_searchable_combo(QComboBox())
        for project_id, project_name in self.project_service.get_project_options(self._selected_owner_id()):
            project_box.addItem(display_project_name(project_name), project_id)
        selected_project = expense.project_id if expense else self.project_filter.currentData()
        index = project_box.findData(selected_project)
        if index >= 0:
            project_box.setCurrentIndex(index)
        date_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        if expense:
            date_edit.setDate(expense.expense_date)
        person_edit = QLineEdit((expense.travel_person or "") if expense else "")
        person_edit.setMaxLength(100)
        start_date_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        end_date_edit = configure_date_edit(ClickableDateEdit(QDate.currentDate()))
        if expense and expense.travel_start_date:
            start_date_edit.setDate(expense.travel_start_date)
        if expense and expense.travel_end_date:
            end_date_edit.setDate(expense.travel_end_date)
        breakdown = self.expense_service.amount_breakdown(expense) if expense else {
            "assessment_fee": 0.0, "actual_cost": 0.0
        }
        assessment_edit = QLineEdit(f"{breakdown['assessment_fee']:.2f}")
        actual_cost_edit = QLineEdit(f"{breakdown['actual_cost']:.2f}")
        for amount_edit in (assessment_edit, actual_cost_edit):
            amount_edit.setValidator(QDoubleValidator(0.0, 99999999.99, 2, self))
            amount_edit.setMaxLength(16)
        preview_label = QLabel()
        preview_label.setObjectName("expenseLineProfitPreview")
        preview_label.setWordWrap(True)
        preview_label.setMinimumHeight(58)
        preview_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        preview_label.setStyleSheet(
            "color: #315d9a; background: #edf4ff; border: 1px solid #d7e6ff;"
            " border-radius: 6px; padding: 8px 10px; font-weight: 700;"
        )

        def refresh_preview():
            try:
                assessment_fee = float(assessment_edit.text().strip() or 0)
                actual_cost = float(actual_cost_edit.text().strip() or 0)
            except ValueError:
                assessment_fee, actual_cost = 0.0, 0.0
            profit = assessment_fee - actual_cost
            preview_label.setText(
                f"考核费用 {assessment_fee:.2f}  |  出差费用 {actual_cost:.2f}\n"
                f"本条利润 {profit:.2f}"
            )

        assessment_edit.textChanged.connect(refresh_preview)
        actual_cost_edit.textChanged.connect(refresh_preview)
        refresh_preview()
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
                ("项目 *", project_box), ("费用日期 *", date_edit),
                ("考核费用", assessment_edit), ("出差费用", actual_cost_edit),
                ("出差人员", person_edit),
                ("出差开始", start_date_edit),
                ("出差结束", end_date_edit),
                ("本条计算", preview_label),
                ("备注", remark_edit), ("报销状态", reimburse_box),
            ],
            columns=2, field_width=330, width=820, height=580, parent=self,
        )

        def save():
            payload = {
                "project_id": project_box.currentData(),
                "expense_date": date_edit.date().toPython(),
                "assessment_fee": assessment_edit.text().strip() or "0",
                "actual_cost": actual_cost_edit.text().strip() or "0",
                "travel_person": person_edit.text().strip(),
                "travel_start_date": start_date_edit.date().toPython(),
                "travel_end_date": end_date_edit.date().toPython(),
                "remarks": remark_edit.text().strip(),
                "is_reimbursed": reimburse_box.currentText(),
            }
            try:
                if expense:
                    self.expense_service.update_expense(expense.id, **payload)
                else:
                    self.expense_service.create_expense(
                        expense_type="费用", amount="0", **payload
                    )
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
