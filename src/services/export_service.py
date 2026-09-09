from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.models import DailyReport, Expense, Machine, Project, get_session
from src.utils.validators import ValidationError
from src.config import resolve_db_path


class ExportService:
    MACHINE_FIELDS = [
        ("角色", "role"), ("管理网IP", "ip"), ("业务网IP", "business_ip"),
        ("集群网IP", "cluster_ip"), ("存储网IP", "storage_ip"), ("计算网IP", "compute_ip"),
        ("用户名", "username"), ("密码", "password"), ("主机名", "hostname"), ("OS", "os"), ("CPU", "cpu"),
        ("内存", "memory"), ("GPU数量", "gpu_count"), ("GPU型号", "gpu_model"),
        ("GPU互联", "gpu_interconnect"), ("CUDA", "cuda"), ("Docker", "docker"),
    ]

    def export_project(self, project_id: int, file_path: str, file_format: str, include_passwords: bool = True) -> str:
        return self.export_projects([project_id], file_path, file_format, include_passwords=include_passwords)

    def export_database(self, file_path: str) -> str:
        source = Path(resolve_db_path())
        if not source.exists():
            raise ValidationError("本地数据库不存在")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() == source.resolve():
            raise ValidationError("不能覆盖当前正在使用的数据库")
        target.write_bytes(source.read_bytes())
        return str(target)

    def export_projects(self, project_ids, file_path: str, file_format: str, *, include_projects=True,
                        include_machines=True, include_reports=True, include_expenses=True,
                        include_passwords=True) -> str:
        data = self._load_projects_data(project_ids)
        if not include_passwords:
            for machine in data["machines"]:
                machine.pop("password", None)
            machine_fields = [(label, field) for label, field in self.MACHINE_FIELDS if field != "password"]
        else:
            machine_fields = self.MACHINE_FIELDS
        data["machine_fields"] = machine_fields
        data["include_projects"] = include_projects
        data["include_machines"] = include_machines
        data["include_reports"] = include_reports
        data["include_expenses"] = include_expenses
        fmt = file_format.lower().lstrip(".")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "xlsx":
            self._write_excel(data, target)
        elif fmt == "docx":
            self._write_word(data, target)
        elif fmt == "zip":
            self._write_zip(data, target)
        else:
            raise ValidationError("仅支持 Excel (.xlsx)、Word (.docx) 或 ZIP (.zip) 格式")
        return str(target)

    def _load_project_data(self, project_id: int) -> dict:
        return self._load_projects_data([project_id])["single"]

    def _load_projects_data(self, project_ids=None) -> dict:
        session = get_session()
        try:
            query = session.query(Project).order_by(Project.id)
            if project_ids is not None:
                query = query.filter(Project.id.in_(list(project_ids)))
            projects = query.all()
            if not projects:
                raise ValidationError("项目不存在")
            ids = [project.id for project in projects]
            project_values = [self._values(project, ["name", "customer", "project_code", "location", "start_date", "end_date", "sales", "status", "remarks"]) for project in projects]
            labels = {project.id: f"{project.name} / {project.project_code or '-'}" for project in projects}
            machines = [self._values(row, [field for _, field in self.MACHINE_FIELDS]) | {"project_label": labels.get(row.project_id, "-")} for row in session.query(Machine).filter(Machine.project_id.in_(ids)).all()]
            reports = [self._values(row, ["report_date", "work_content", "problems", "solutions", "next_plan", "remarks", "status"]) | {"project_label": labels.get(row.project_id, "-")} for row in session.query(DailyReport).filter(DailyReport.project_id.in_(ids)).order_by(DailyReport.report_date).all()]
            expenses = [self._values(row, ["expense_date", "expense_type", "amount", "remarks", "is_reimbursed"]) | {"project_label": labels.get(row.project_id, "-")} for row in session.query(Expense).filter(Expense.project_id.in_(ids)).order_by(Expense.expense_date).all()]
            data = {"projects": project_values, "project": project_values[0], "machines": machines, "reports": reports, "expenses": expenses, "project_labels": labels}
            data["single"] = data
            return data
        finally:
            session.close()

    @staticmethod
    def _values(model, fields):
        return {field: getattr(model, field, None) for field in fields}

    def _write_excel(self, data: dict, path: Path):
        workbook = Workbook()
        workbook.remove(workbook.active)
        project_fields = [("项目客户名称", "name"), ("销售", "sales"), ("订单编号", "project_code"), ("实施地点", "location"), ("开始日期", "start_date"), ("结束日期", "end_date"), ("项目状态", "status"), ("备注", "remarks")]
        if data.get("include_projects", True): self._add_sheet(workbook, "项目", project_fields, data["projects"])
        if data.get("include_machines", True): self._add_sheet(workbook, "机器", [("所属项目", "project_label"), *data.get("machine_fields", self.MACHINE_FIELDS)], data["machines"])
        if data.get("include_reports", True): self._add_sheet(workbook, "SOP问题", [("所属项目", "project_label"), ("日期", "report_date"), ("SOP主题/步骤", "work_content"), ("遇到的问题", "problems"), ("解决方法", "solutions"), ("后续建议", "next_plan"), ("备注", "remarks"), ("状态", "status")], data["reports"])
        if data.get("include_expenses", True): self._add_sheet(workbook, "出差费用", [("所属项目", "project_label"), ("日期", "expense_date"), ("类型", "expense_type"), ("金额", "amount"), ("备注", "remarks"), ("报销状态", "is_reimbursed")], data["expenses"])
        workbook.save(path)

    @staticmethod
    def _add_sheet(workbook, title, fields, rows):
        sheet = workbook.create_sheet(title)
        sheet.append([label for label, _ in fields])
        fill = PatternFill("solid", fgColor="DCE8F8")
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = fill
        for row in rows:
            sheet.append(["" if row.get(field) is None else row.get(field) for _, field in fields])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(sheet.columns, start=1):
            width = min(45, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[get_column_letter(index)].width = width

    def _write_word(self, data: dict, path: Path):
        document = Document()
        project = data["project"]
        document.add_heading(project.get("name") or "项目实施资料", level=0)
        document.add_heading("项目基本信息", level=1)
        for label, value in [
            ("客户", project.get("customer")), ("项目编号", project.get("project_code")),
            ("地点", project.get("location")), ("实施周期", f"{project.get('start_date') or ''} 至 {project.get('end_date') or ''}"),
            ("销售", project.get("sales")), ("状态", project.get("status")),
        ]:
            document.add_paragraph(f"{label}：{value or ''}")
        document.add_heading(f"机器信息（{len(data['machines'])} 台）", level=1)
        for machine in data["machines"]:
            document.add_heading(machine.get("hostname") or machine.get("ip") or "机器", level=2)
            document.add_paragraph("；".join(f"{label}：{machine.get(field) or ''}" for label, field in data.get("machine_fields", self.MACHINE_FIELDS)))
        document.add_heading(f"SOP问题记录（{len(data['reports'])} 条）", level=1)
        for report in data["reports"]:
            document.add_heading(str(report.get("report_date") or ""), level=2)
            for label, field in [("SOP主题/步骤", "work_content"), ("遇到的问题", "problems"), ("解决方法", "solutions"), ("后续建议", "next_plan"), ("备注", "remarks")]:
                document.add_paragraph(f"{label}：{report.get(field) or ''}")
        document.add_heading(f"出差费用（{len(data['expenses'])} 条）", level=1)
        total = sum(float(row.get("amount") or 0) for row in data["expenses"])
        document.add_paragraph(f"费用合计：{total:.2f} 元")
        for expense in data["expenses"]:
            document.add_paragraph(f"{expense.get('expense_date')} | {expense.get('expense_type')} | {float(expense.get('amount') or 0):.2f} 元 | {expense.get('remarks') or ''}")
        document.save(path)

    def _write_zip(self, data: dict, path: Path):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            excel_path = temp_path / "项目数据.xlsx"
            word_path = temp_path / "项目实施资料.docx"
            markdown_path = temp_path / "SOP问题记录.md"
            self._write_excel(data, excel_path)
            self._write_word(data, word_path)
            markdown_path.write_text(self._reports_markdown(data), encoding="utf-8")
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                archive.write(excel_path, "01_项目数据/项目数据.xlsx")
                archive.write(word_path, "02_实施资料/项目实施资料.docx")
                archive.write(markdown_path, "03_SOP问题记录/SOP问题记录.md")

    @staticmethod
    def _reports_markdown(data: dict) -> str:
        lines = [f"# {data['project'].get('name') or '项目'}SOP问题记录", ""]
        for report in data["reports"]:
            lines.extend([f"## {report.get('report_date') or ''}", f"- SOP主题/步骤：{report.get('work_content') or ''}", f"- 遇到的问题：{report.get('problems') or ''}", f"- 解决方法：{report.get('solutions') or ''}", f"- 后续建议：{report.get('next_plan') or ''}", ""])
        return "\n".join(lines)
