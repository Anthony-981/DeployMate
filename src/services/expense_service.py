from typing import List
from datetime import date
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from src.models import Expense, get_session
from src.utils.validators import (
    EXPENSE_FIELD_LIMITS,
    ValidationError,
    optional_text,
    require_text,
    validate_choice,
    validate_positive_amount,
)

class ExpenseService:
    def get_expenses_page(self, page=1, page_size=20, project_id=None):
        session = get_session()
        try:
            query = session.query(Expense)
            if project_id:
                query = query.filter(Expense.project_id == project_id)
            query = query.order_by(Expense.expense_date.desc())
            return query.count(), query.offset((page - 1) * page_size).limit(page_size).all()
        finally:
            session.close()
    def get_expenses_by_project(self, project_id: int) -> List[Expense]:
        session = get_session()
        try:
            return (
                session.query(Expense)
                .filter(Expense.project_id == project_id)
                .order_by(Expense.expense_date.desc())
                .all()
            )
        finally:
            session.close()

    def get_all_expenses(self) -> List[Expense]:
        session = get_session()
        try:
            return session.query(Expense).order_by(Expense.expense_date.desc()).all()
        finally:
            session.close()

    def get_expense_by_id(self, expense_id: int) -> Expense | None:
        session = get_session()
        try:
            return session.query(Expense).filter(Expense.id == expense_id).first()
        finally:
            session.close()

    def create_expense(
        self,
        project_id: int,
        expense_date: date,
        expense_type: str,
        amount,
        remarks: str = None,
        is_reimbursed: str = "未提交",
    ) -> Expense:
        session = get_session()
        try:
            if not project_id or int(project_id) <= 0:
                raise ValidationError("项目不能为空")
            expense_type = validate_choice(expense_type, "费用类型", {"交通", "住宿", "餐费", "打车", "其他"})
            amount = validate_positive_amount(amount, "金额")
            remarks = optional_text(remarks, "备注", EXPENSE_FIELD_LIMITS["remarks"])
            is_reimbursed = validate_choice(is_reimbursed, "报销状态", {"未提交", "已提交", "已报销"})

            expense = Expense(
                project_id=project_id,
                expense_date=expense_date,
                expense_type=expense_type,
                amount=amount,
                remarks=remarks,
                is_reimbursed=is_reimbursed,
            )
            session.add(expense)
            session.commit()
            session.refresh(expense)
            return expense
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_expense(self, expense_id: int, **kwargs) -> Expense | None:
        session = get_session()
        try:
            expense = session.query(Expense).filter(Expense.id == expense_id).first()
            if not expense:
                return None
            for key, value in kwargs.items():
                if hasattr(expense, key):
                    if key == "expense_type":
                        value = validate_choice(value, "费用类型", {"交通", "住宿", "餐费", "打车", "其他"})
                    elif key == "amount":
                        value = validate_positive_amount(value, "金额")
                    elif key == "remarks":
                        value = optional_text(value, "备注", EXPENSE_FIELD_LIMITS["remarks"])
                    elif key == "is_reimbursed":
                        value = validate_choice(value, "报销状态", {"未提交", "已提交", "已报销"})
                    setattr(expense, key, value)
            session.commit()
            session.refresh(expense)
            return expense
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_expense(self, expense_id: int) -> bool:
        session = get_session()
        try:
            expense = session.query(Expense).filter(Expense.id == expense_id).first()
            if not expense:
                return False
            session.delete(expense)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_all_expenses(self) -> int:
        session = get_session()
        try:
            count = session.query(Expense).count()
            session.query(Expense).delete(synchronize_session=False)
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_total_amount(self, project_id: int | None):
        session = get_session()
        try:
            query = session.query(Expense)
            if project_id:
                query = query.filter(Expense.project_id == project_id)
            rows = query.all()
            return sum(float(item.amount) for item in rows)
        finally:
            session.close()

    def export_expenses(self, project_id: int, file_path: str) -> str:
        expenses = self.get_expenses_by_project(project_id)
        if not expenses:
            raise ValidationError("当前项目暂无费用可导出")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "出差费用"
        headers = ["日期", "费用类型", "金额", "备注", "报销状态"]
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DCE8F8")
        for expense in expenses:
            sheet.append([
                expense.expense_date,
                expense.expense_type,
                float(expense.amount),
                expense.remarks or "",
                expense.is_reimbursed or "",
            ])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(sheet.columns, start=1):
            width = min(45, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[get_column_letter(index)].width = width
        workbook.save(target)
        return str(target)
