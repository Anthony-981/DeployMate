import json
from pathlib import Path
from openpyxl import load_workbook
from csv import DictReader
from src.utils.field_mapper import normalize_field_name
from src.utils.field_mapper import normalize_machine_header
from src.models import ImportFile, ImportRow, Project, get_session
from src.services.machine_service import MachineService
from src.services.project_service import ProjectService
from src.utils.validators import MACHINE_FIELD_LIMITS, ValidationError, validate_ipv4
from src.ui.widgets.common import display_project_name
import re

IP_RE = re.compile(r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)")

class ImportService:
    def __init__(self):
        self.last_sheet_scan = []

    def get_import_history(self, limit: int = 50, page: int = 1, page_size: int | None = None):
        session = get_session()
        try:
            query = (
                session.query(ImportFile, Project.name, Project.project_code)
                .join(Project, Project.id == ImportFile.project_id)
                .order_by(ImportFile.imported_at.desc())
            )
            total = query.count()
            query = query.limit(page_size or limit)
            if page_size:
                query = query.offset((page - 1) * page_size)
            rows = query.all()
            result = [
                {
                    "project": display_project_name(project_name),
                    "file_name": record.file_name,
                    "records": record.records_count,
                    "new": record.new_count,
                    "merge": record.merge_count,
                    "conflict": record.conflict_count,
                    "status": record.status,
                    "imported_at": record.imported_at.strftime("%Y-%m-%d %H:%M:%S") if record.imported_at else "",
                }
                for record, project_name, project_code in rows
            ]
            return (total, result) if page_size else result
        finally:
            session.close()

    def read_file(self, file_path: str):
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return self._read_xlsx(path)
        if suffix == ".csv":
            return self._read_csv(path)
        raise ValidationError("仅支持 Excel (.xlsx) 和 CSV (.csv) 文件")

    def read_file_groups(self, file_path: str) -> list[dict]:
        """Read one or more machine tables, preserving XLSX worksheet names."""
        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            rows = self._read_csv(path)
            self.last_sheet_scan = [{"sheet_name": "CSV数据", "records": len(rows), "status": "已识别，待导入"}]
            return [{"sheet_name": "CSV数据", "rows": rows}]
        if path.suffix.lower() != ".xlsx":
            raise ValidationError("仅支持 Excel (.xlsx) 和 CSV (.csv) 文件")
        workbook = load_workbook(path, data_only=True, read_only=True)
        try:
            groups = []
            self.last_sheet_scan = []
            workbook_metadata = {}
            for worksheet in workbook.worksheets:
                rows = list(worksheet.iter_rows(values_only=True))
                if not rows or not any(value not in (None, "") for row in rows for value in row):
                    self.last_sheet_scan.append({
                        "sheet_name": worksheet.title, "records": 0, "status": "已跳过：空白工作表"
                    })
                    continue
                metadata = self._extract_project_metadata(rows)
                for key, value in metadata.items():
                    workbook_metadata.setdefault(key, value)
                try:
                    header_index, headers = self._find_header_row(rows)
                except ValidationError as exc:
                    # Non-machine sheets are still retained losslessly.
                    source_rows = [
                        {f"列{index + 1}": value for index, value in enumerate(raw) if value not in (None, "")}
                        for raw in rows
                        if any(value not in (None, "") for value in raw)
                    ]
                    groups.append({
                        "sheet_name": worksheet.title,
                        "rows": [],
                        "source_rows": source_rows,
                        "project_metadata": {**workbook_metadata, **metadata},
                    })
                    self.last_sheet_scan.append({
                        "sheet_name": worksheet.title,
                        "records": len(source_rows),
                        "status": f"已读取 {len(source_rows)} 行，原始内容已保存",
                    })
                    continue
                result = []
                source_rows = [
                    raw for raw in rows[header_index + 1:]
                    if any(value not in (None, "") for value in raw)
                ]
                for raw in source_rows:
                    item = self._build_machine_row(headers, raw)
                    if item:
                        result.append(item)
                if result or source_rows:
                    groups.append({
                        "sheet_name": worksheet.title,
                        "rows": result,
                        "source_rows": source_rows,
                        "project_metadata": {**workbook_metadata, **metadata},
                    })
                    self.last_sheet_scan.append({
                        "sheet_name": worksheet.title,
                        "records": len(source_rows),
                        "status": f"已读取 {len(source_rows)} 行，机器记录 {len(result)} 条，待导入",
                    })
                else:
                    self.last_sheet_scan.append({
                        "sheet_name": worksheet.title, "records": 0, "status": "已读取，无数据行"
                    })
            if not groups:
                raise ValidationError(
                    "未识别到任何包含机器信息的工作表，请确认至少一个子表包含角色及业务网IP/集群网IP等字段"
                )
            for group in groups:
                group["project_metadata"] = {**workbook_metadata, **group.get("project_metadata", {})}
            return groups
        finally:
            workbook.close()

    def get_project_label(self, project_id: int) -> str:
        session = get_session()
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            return display_project_name(project.name) if project else "未知项目"
        finally:
            session.close()

    def get_or_create_import_project(self, sheet_name: str, file_stem: str, index: int, metadata: dict | None = None) -> int:
        """Match a project by the worksheet customer name, creating it when absent."""
        source_name = (sheet_name or file_stem or f"导入客户{index + 1}").strip()[:100]
        parts = re.split(r"\s*[-－—_/\\]\s*", source_name, maxsplit=1)
        project_name = parts[0].strip() or source_name
        sales_name = parts[1].strip() if len(parts) > 1 else ""
        # A sheet named "湘南学院-李华敏" is treated as project "湘南学院"
        # with the suffix mapped to the salesperson; do not duplicate it into 客户.
        customer_name = "" if sales_name else project_name
        metadata = metadata or {}
        sales_name = (metadata.get("sales") or sales_name).strip()[:100]
        location_name = str(metadata.get("location") or "").strip()[:100]
        session = get_session()
        try:
            existing = session.query(Project).filter(Project.customer == customer_name).first() if customer_name else None
            if not existing:
                # Keep compatibility with projects created by earlier DeployMate versions.
                existing = session.query(Project).filter(Project.name == project_name).first()
            if not existing and source_name != project_name:
                existing = session.query(Project).filter(Project.name == source_name).first()
                if existing:
                    existing.name = project_name
                    existing.customer = customer_name
                    existing.sales = sales_name or existing.sales
                    existing.location = location_name or existing.location
                    session.commit()
            if existing:
                if sales_name:
                    existing.customer = ""
                if sales_name:
                    existing.sales = sales_name
                if location_name and not existing.location:
                    existing.location = location_name
                if sales_name or location_name:
                    session.commit()
                return existing.id
        finally:
            session.close()
        project = ProjectService().create_project(
                name=project_name,
                customer=customer_name,
                sales=sales_name or None,
                    location=location_name or None,
                    project_code=None,
                    status="待开始",
                )
        return project.id

    @staticmethod
    def _extract_project_metadata(rows):
        """Read project-level sales/location values from label-value cells."""
        aliases = {
            "sales": {"销售", "销售人员", "销售姓名", "sales"},
            "location": {"地点", "实施地点", "项目地点", "所在地", "location"},
        }
        label_values = set().union(*aliases.values()) | {"实施时间", "日期", "时间"}
        metadata = {}
        limited_rows = rows[:80]
        for row_index, row in enumerate(limited_rows):
            values = ["" if value is None else str(value).strip() for value in row]
            for index, value in enumerate(values):
                compact = re.sub(r"[\s:：()（）]", "", value).lower()
                for field, names in aliases.items():
                    if compact not in names or field in metadata:
                        continue
                    candidates = [
                        item for item in values[index + 1:] + values[:index]
                        if item and item.lower() not in label_values
                    ]
                    if not any(candidates):
                        candidates = [
                            "" if index >= len(next_row) or next_row[index] is None
                            else str(next_row[index]).strip()
                            for next_row in limited_rows[row_index + 1:row_index + 4]
                        ]
                    candidate = next((item for item in candidates if item), "")
                    if candidate and not IP_RE.fullmatch(candidate):
                        metadata[field] = candidate
        return metadata

    @staticmethod
    def combine_results(results: list[dict]) -> dict:
        combined = {"records": 0, "new": 0, "merge": 0, "conflict": 0, "errors": [], "conflicts": []}
        for result in results:
            for key in ("records", "new", "merge", "conflict"):
                combined[key] += result.get(key, 0)
            combined["errors"].extend(result.get("errors", []))
            combined["conflicts"].extend(result.get("conflicts", []))
        return combined

    def _read_xlsx(self, path: Path):
        wb = load_workbook(path, data_only=True, read_only=True)
        try:
            rows = list(wb.active.iter_rows(values_only=True))
            if not rows:
                return []
            header_index, headers = self._find_header_row(rows)
            result = []
            for raw in rows[header_index + 1:]:
                if self._header_score(raw) >= 2:
                    continue
                item = self._build_machine_row(headers, raw)
                if item:
                    result.append(item)
            return result
        finally:
            wb.close()

    def _read_csv(self, path: Path):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = DictReader(f)
            result = []
            for row in reader:
                item = self._build_machine_row(
                    [normalize_machine_header(key) for key in row.keys()],
                    list(row.values()),
                )
                if item:
                    result.append(item)
            return result

    def _find_header_row(self, rows):
        network_fields = {"ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip"}
        candidates = []
        for index, row in enumerate(rows[:200]):
            headers = [normalize_machine_header(value) for value in row]
            fields = {field for mapped in headers for field in mapped}
            candidates.append((bool(fields & network_fields), len(fields), index, headers))
        has_network, _score, header_index, headers = max(
            candidates, key=lambda item: (item[0], item[1]), default=(False, 0, 0, [])
        )
        if not has_network:
            raise ValidationError("未找到 IP/网络列")
        return header_index, headers

    @staticmethod
    def _header_score(row) -> int:
        known = 0
        for value in row:
            if normalize_machine_header(value):
                known += 1
        return known

    @staticmethod
    def _build_machine_row(headers, raw):
        item = {}
        unknown_values = []
        for index, value in enumerate(raw):
            if index >= len(headers) or value in (None, ""):
                continue
            fields = headers[index]
            if not fields:
                unknown_values.append(f"列{index + 1}={value}")
                continue
            text_value = str(value).strip()
            ips = IP_RE.findall(text_value)
            for field in fields:
                if field in {"ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip"}:
                    if ips:
                        item[field] = ips[0]
                elif field == "gpu_count" and text_value in {"无", "无GPU", "-"}:
                    continue
                elif field == "gpu_model" and text_value in {"无", "-"}:
                    continue
                else:
                    item[field] = value
        if unknown_values:
            existing = str(item.get("remarks") or "").strip()
            extra = "；".join(unknown_values)
            item["remarks"] = f"{existing}；{extra}".strip("；")
        # Many implementation sheets do not have a management IP column.
        if not item.get("ip"):
            item["ip"] = next(
                (item[field] for field in ("business_ip", "cluster_ip", "compute_ip", "storage_ip") if item.get(field)),
                "",
            )
        if not item["ip"]:
            return {}
        return item

    def import_machines(self, project_id: int, rows: list[dict], file_name: str,
                        file_type: str = "", file_size: int = 0,
                        source_rows: list[dict] | None = None,
                        sheet_name: str = "导入数据") -> dict:
        """将导入记录按项目/IP写入机器表，已有机器只补充空字段。"""
        if not project_id:
            raise ValidationError("请先选择项目")

        session = get_session()
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValidationError("目标项目不存在，请刷新项目列表后重新选择")
            project_name = project.name
        finally:
            session.close()

        machine_service = MachineService()
        allowed_fields = set(MACHINE_FIELD_LIMITS) | {"account"}
        summary = {"records": len(rows), "new": 0, "merge": 0, "conflict": 0, "errors": []}
        conflicts = []

        for row_number, raw_row in enumerate(rows, start=2):
            row = {key: value for key, value in raw_row.items() if key in allowed_fields or key == "ip"}
            try:
                ip = validate_ipv4(row.pop("ip", ""), "IP", required=True)
                machine, is_new, row_conflicts = machine_service.merge_machine_data(
                    project_id, ip, row
                )
                if is_new:
                    summary["new"] += 1
                else:
                    summary["merge"] += 1
                for field, values in row_conflicts.items():
                    summary["conflict"] += 1
                    conflicts.append({
                        "row": row_number,
                        "ip": ip,
                        "field": field,
                        "old": values["old"],
                        "new": values["new"],
                        "action": "已保留原值",
                    })
            except Exception as exc:
                summary["errors"].append({"row": row_number, "message": str(exc), "data": dict(raw_row), "project_id": project_id})

        session = get_session()
        try:
            record = ImportFile(
                project_id=project_id,
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                records_count=summary["records"],
                new_count=summary["new"],
                merge_count=summary["merge"],
                conflict_count=summary["conflict"],
                status="已完成" if not summary["errors"] else "部分完成",
            )
            session.add(record)
            session.flush()
            for row_number, raw_row in enumerate(source_rows or rows, start=2):
                session.add(ImportRow(
                    project_id=project_id,
                    file_name=file_name,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    row_json=json.dumps(raw_row, ensure_ascii=False, default=str),
                    import_status="机器已写入" if raw_row in rows else "原始数据已保存",
                ))
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return {**summary, "conflicts": conflicts, "project_id": project_id, "project_name": project_name}
