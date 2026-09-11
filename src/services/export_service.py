from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.models import DailyReport, Expense, Machine, Project, get_session
from src.services.access_service import scope_query
from src.utils.validators import ValidationError
from src.config import resolve_db_path


class ExportService:
    MACHINE_FIELDS = [
        ("角色", "role"), ("管理网IP", "ip"), ("业务网IP", "business_ip"),
        ("集群网IP", "cluster_ip"), ("存储网IP", "storage_ip"), ("计算网IP", "compute_ip"),
        ("用户名", "username"), ("密码", "password"), ("主机名", "hostname"), ("OS", "os"), ("CPU", "cpu"),
        ("内存", "memory"), ("GPU数量", "gpu_count"), ("GPU型号", "gpu_model"),
        ("GPU互联", "gpu_interconnect"), ("CUDA", "cuda"), ("Docker", "docker"),
        ("备注", "remarks"), ("其他信息", "extra_info"),
    ]

    def __init__(self, current_user=None):
        self.current_user = current_user

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
        elif fmt == "md":
            self._write_markdown(data, target)
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
            query = scope_query(session.query(Project), Project, self.current_user).order_by(Project.id)
            if project_ids is not None:
                query = query.filter(Project.id.in_(list(project_ids)))
            projects = query.all()
            if not projects:
                raise ValidationError("项目不存在")
            ids = [project.id for project in projects]
            project_values = [
                self._values(
                    project,
                    ["id", "name", "customer", "project_code", "location", "start_date",
                     "end_date", "sales", "status", "remarks"],
                )
                for project in projects
            ]
            labels = {project.id: f"{project.name} / {project.project_code or '-'}" for project in projects}
            machines = [
                self._values(row, ["id", "project_id", *[field for _, field in self.MACHINE_FIELDS]])
                | {"project_label": labels.get(row.project_id, "-")}
                for row in session.query(Machine).filter(Machine.project_id.in_(ids)).all()
            ]
            reports = [
                self._values(row, ["id", "project_id", "report_date", "work_content", "problems",
                                   "solutions", "next_plan", "remarks", "status"])
                | {"project_label": labels.get(row.project_id, "-")}
                for row in session.query(DailyReport).filter(DailyReport.project_id.in_(ids)).order_by(DailyReport.report_date).all()
            ]
            expenses = [
                self._values(row, [
                    "id", "project_id", "expense_date", "travel_person",
                    "travel_start_date", "travel_end_date", "expense_category",
                    "expense_type",
                    "amount", "remarks", "is_reimbursed",
                ])
                | {"project_label": labels.get(row.project_id, "-")}
                for row in session.query(Expense).filter(Expense.project_id.in_(ids)).order_by(Expense.expense_date).all()
            ]
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
        if data.get("include_machines", True):
            self._add_sheet(
                workbook, "机器",
                [("所属项目", "project_label"), *data.get("machine_fields", self.MACHINE_FIELDS)],
                data["machines"],
            )
        if data.get("include_reports", True): self._add_sheet(workbook, "SOP问题", [("所属项目", "project_label"), ("日期", "report_date"), ("SOP主题/步骤", "work_content"), ("遇到的问题", "problems"), ("解决方法", "solutions"), ("后续建议", "next_plan"), ("备注", "remarks"), ("状态", "status")], data["reports"])
        if data.get("include_expenses", True):
            self._add_sheet(
                workbook,
                "出差费用",
                [
                    ("所属项目", "project_label"), ("费用日期", "expense_date"),
                    ("出差人员", "travel_person"), ("出差开始", "travel_start_date"),
                    ("出差结束", "travel_end_date"), ("费用分类", "expense_category"),
                    ("金额", "amount"), ("备注", "remarks"), ("报销状态", "is_reimbursed"),
                ],
                data["expenses"],
            )
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
            sheet.append([
                ExportService._export_value(row.get(field))
                for _, field in fields
            ])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(sheet.columns, start=1):
            width = min(52, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[get_column_letter(index)].width = width

    @staticmethod
    def _export_value(value):
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            import json
            return json.dumps(value, ensure_ascii=False)
        return value

    def _write_word(self, data: dict, path: Path):
        document = Document()
        self._configure_document(document)
        document.add_heading("项目实施资料", level=0)
        document.add_paragraph(f"生成时间：{datetime.now():%Y-%m-%d %H:%M}")
        for project in data["projects"]:
            project_id = project.get("id")
            project_label = f"{project.get('name') or '未命名项目'} / {project.get('project_code') or '-'}"
            document.add_heading(project.get("name") or "未命名项目", level=1)
            if data.get("include_projects", True):
                document.add_heading("项目基本信息", level=2)
                self._add_word_table(document, ["字段", "内容"], [
                    ("客户", project.get("customer")), ("项目编号", project.get("project_code")),
                    ("地点", project.get("location")),
                    ("实施周期", f"{project.get('start_date') or ''} 至 {project.get('end_date') or ''}"),
                    ("销售", project.get("sales")), ("状态", project.get("status")),
                    ("备注", project.get("remarks")),
                ])
            machines = [row for row in data["machines"] if row.get("project_id") == project_id]
            reports = [row for row in data["reports"] if row.get("project_id") == project_id]
            expenses = [row for row in data["expenses"] if row.get("project_id") == project_id]
            if data.get("include_machines", True):
                document.add_heading(f"机器信息（{len(machines)} 台）", level=2)
                for machine in machines:
                    machine_title = machine.get("hostname") or machine.get("ip") or "机器"
                    document.add_heading(machine_title, level=3)
                    self._add_word_table(
                        document, ["字段", "内容"],
                        [(label, self._export_value(machine.get(field))) for label, field in data["machine_fields"]],
                    )
            if data.get("include_reports", True):
                document.add_heading(f"SOP问题记录（{len(reports)} 条）", level=2)
                if reports:
                    for report in reports:
                        document.add_heading(
                            f"{report.get('report_date') or '-'} · {report.get('status') or '未填写'}",
                            level=3,
                        )
                        self._add_word_table(document, ["字段", "内容"], [
                            ("主题/步骤", report.get("work_content")),
                            ("遇到的问题", report.get("problems")),
                            ("解决方法", report.get("solutions")),
                            ("后续建议", report.get("next_plan")),
                            ("备注", report.get("remarks")),
                        ])
                else:
                    self._add_word_table(document, ["字段", "内容"], [("记录", "暂无记录")])
            if data.get("include_expenses", True):
                total = sum(float(row.get("amount") or 0) for row in expenses)
                document.add_heading(f"出差费用（{len(expenses)} 条，合计 {total:.2f} 元）", level=2)
                self._add_word_table(document, [
                    "费用日期", "出差人员", "出差开始", "出差结束",
                    "费用分类", "金额（元）", "备注", "报销状态",
                ], [
                    (expense.get("expense_date") or "-", expense.get("travel_person") or "-",
                     expense.get("travel_start_date") or "-", expense.get("travel_end_date") or "-",
                     expense.get("expense_category") or "-",
                     f"{float(expense.get('amount') or 0):.2f}", expense.get("remarks") or "-",
                     expense.get("is_reimbursed") or "-")
                    for expense in expenses
                ])
        document.save(path)

    @staticmethod
    def _configure_document(document):
        styles = document.styles
        styles["Normal"].font.name = "Microsoft YaHei"
        styles["Normal"].font.size = Pt(10)
        styles["Normal"].paragraph_format.space_after = Pt(4)
        styles["Normal"].paragraph_format.line_spacing = 1.15
        for style_name, size, color in (
            ("Title", 22, "17365D"),
            ("Heading 1", 17, "17365D"),
            ("Heading 2", 13, "2F5597"),
            ("Heading 3", 11, "5B6B83"),
        ):
            style = styles[style_name]
            style.font.name = "Microsoft YaHei"
            style.font.size = Pt(size)
            style.font.bold = True
            style.font.color.rgb = RGBColor.from_string(color)
        for section in document.sections:
            section.top_margin = Inches(0.65)
            section.bottom_margin = Inches(0.65)
            section.left_margin = Inches(0.7)
            section.right_margin = Inches(0.7)

    @staticmethod
    def _add_word_table(document, headers, rows):
        table = document.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        table.autofit = True
        for cell, header in zip(table.rows[0].cells, headers):
            cell.text = str(header)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for run in cell.paragraphs[0].runs:
                run.bold = True
                run.font.name = "Microsoft YaHei"
                run.font.size = Pt(9)
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
        tr_pr = table.rows[0]._tr.get_or_add_trPr()
        tbl_header = OxmlElement("w:tblHeader")
        tbl_header.set(qn("w:val"), "true")
        tr_pr.append(tbl_header)
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = ExportService._display_value(value)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = Pt(0)
                    for run in paragraph.runs:
                        run.font.name = "Microsoft YaHei"
                        run.font.size = Pt(9)
        if not rows:
            cells = table.add_row().cells
            cells[0].merge(cells[-1])
            cells[0].text = "暂无记录"

    def _write_markdown(self, data: dict, path: Path):
        path.write_text(self._build_markdown(data), encoding="utf-8")

    def _build_markdown(self, data: dict) -> str:
        lines = [
            "# 项目实施资料", "",
            f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M}", "",
        ]
        for project in data["projects"]:
            project_id = project.get("id")
            machines = [row for row in data["machines"] if row.get("project_id") == project_id]
            reports = [row for row in data["reports"] if row.get("project_id") == project_id]
            expenses = [row for row in data["expenses"] if row.get("project_id") == project_id]
            lines.extend([
                f"## {project.get('name') or '未命名项目'}",
                "",
            ])
            if data.get("include_projects", True):
                lines.extend([
                    "### 项目基本信息", "", "| 字段 | 内容 |", "| --- | --- |",
                    *[f"| {label} | {self._markdown_value(value)} |" for label, value in [
                        ("客户", project.get("customer")), ("项目编号", project.get("project_code")),
                        ("地点", project.get("location")),
                        ("实施周期", f"{project.get('start_date') or ''} 至 {project.get('end_date') or ''}"),
                        ("销售", project.get("sales")), ("状态", project.get("status")),
                        ("备注", project.get("remarks")),
                    ]], "",
                ])
            if data.get("include_machines", True):
                lines.extend(["### 机器信息", ""])
                for machine in machines:
                    lines.extend([
                        f"#### {self._markdown_value(machine.get('hostname') or machine.get('ip') or '机器')}",
                        "",
                        "| 字段 | 内容 |", "| --- | --- |",
                        *[
                            f"| {self._markdown_value(label)} | {self._markdown_value(machine.get(field))} |"
                            for label, field in data["machine_fields"]
                        ],
                        "",
                    ])
                if not machines:
                    lines.append("暂无记录")
            if data.get("include_reports", True):
                lines.extend(["", "### SOP问题记录", "",
                    "| 日期 | 主题/步骤 | 遇到的问题 | 解决方法 | 后续建议 | 状态 |",
                    "| --- | --- | --- | --- | --- | --- |"])
                lines.extend([
                    f"| {self._markdown_value(report.get('report_date'))} | {self._markdown_value(report.get('work_content'))} | "
                    f"{self._markdown_value(report.get('problems'))} | {self._markdown_value(report.get('solutions'))} | "
                    f"{self._markdown_value(report.get('next_plan'))} | {self._markdown_value(report.get('status'))} |"
                    for report in reports
                ] or ["| 暂无记录 | | | | | |"])
            if data.get("include_expenses", True):
                total = sum(float(row.get("amount") or 0) for row in expenses)
                lines.extend(["", f"### 出差费用（合计 {total:.2f} 元）", "",
                    "| 费用日期 | 出差人员 | 出差开始 | 出差结束 | 费用分类 | 金额（元） | 备注 | 报销状态 |",
                    "| --- | --- | --- | --- | --- | ---: | --- | --- |"])
                lines.extend([
                    f"| {self._markdown_value(expense.get('expense_date'))} | {self._markdown_value(expense.get('travel_person'))} | "
                    f"{self._markdown_value(expense.get('travel_start_date'))} | {self._markdown_value(expense.get('travel_end_date'))} | "
                    f"{self._markdown_value(expense.get('expense_category'))} | "
                    f"{float(expense.get('amount') or 0):.2f} | "
                    f"{self._markdown_value(expense.get('remarks'))} | "
                    f"{self._markdown_value(expense.get('is_reimbursed'))} |"
                    for expense in expenses
                ] or ["| 暂无记录 | | | | | | | |"])
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _markdown_value(value):
        return ExportService._display_value(value).replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")

    @staticmethod
    def _display_value(value):
        return "-" if value is None or value == "" else str(value)

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
        return ExportService()._build_markdown(data)
