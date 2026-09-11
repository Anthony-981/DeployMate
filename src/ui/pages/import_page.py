from pathlib import Path
import json
from PySide6.QtCore import QSettings
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QTabWidget,
)

from src.services.import_service import ImportService
from src.services.project_service import ProjectService
from src.ui.widgets.common import FormDialog, PaginationBar, make_button, make_page, make_panel, make_table, show_toast, make_searchable_combo, display_project_name
from src.services.machine_service import MachineService
from src.utils.validators import MACHINE_FIELD_LIMITS, validate_ipv4


class ImportPage(QWidget):
    import_completed = Signal(int)

    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.import_service = ImportService(current_user)
        self.project_service = ProjectService(current_user)
        self.current_rows = []
        self.current_file_path = ""
        self.pending_errors = []
        settings = QSettings("DeployMate", "DeployMate")
        try:
            self.repair_history = json.loads(settings.value("import_repair_history", "[]"))
        except (TypeError, json.JSONDecodeError):
            self.repair_history = []
        self.result_rows = []
        self.conflict_rows = []
        self.raw_rows = []
        self.repair_history_rows = []
        self.build_ui()

    def build_ui(self):
        page, layout, _head = make_page("导入 / 合并", "导入历史资料，自动识别字段，并按 IP 合并机器信息。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(page)

        upload_panel, upload_layout = make_panel("文件导入")
        control_row = QHBoxLayout()
        control_row.setSpacing(12)
        project_label = QLabel("目标项目")
        project_label.setStyleSheet("font-weight: 700; color: #425069;")
        control_row.addWidget(project_label)
        self.project_box = make_searchable_combo(QComboBox())
        self.project_box.setMinimumWidth(340)
        self.project_box.setMaximumWidth(460)
        self.refresh_projects()
        self.project_box.currentIndexChanged.connect(self._update_import_button)
        control_row.addWidget(self.project_box)
        self.auto_project_check = QCheckBox("多工作表按工作表自动创建项目")
        self.auto_project_check.setChecked(True)
        self.auto_project_check.setEnabled(False)
        self.auto_project_check.setFocusPolicy(Qt.NoFocus)
        self.auto_project_check.toggled.connect(self._on_auto_project_changed)
        control_row.addWidget(self.auto_project_check)
        control_row.addStretch()
        self.import_btn = make_button("确认导入", True)
        self.import_btn.setMinimumWidth(108)
        self.import_btn.clicked.connect(self.import_current_file)
        self.import_btn.setEnabled(False)
        control_row.addWidget(self.import_btn)
        self.fix_btn = make_button("逐条修正失败记录")
        self.fix_btn.setEnabled(False)
        self.fix_btn.setVisible(False)
        self.fix_btn.clicked.connect(self.fix_next_error)
        control_row.addWidget(self.fix_btn)
        self.batch_fix_btn = make_button("批量重试可修正记录")
        self.batch_fix_btn.setEnabled(False)
        self.batch_fix_btn.setVisible(False)
        self.batch_fix_btn.clicked.connect(self.batch_fix_errors)
        control_row.addWidget(self.batch_fix_btn)
        upload_layout.addLayout(control_row)

        self.workflow_label = QLabel("1 选择文件  →  2 检查识别结果  →  3 确认导入")
        self.workflow_label.setStyleSheet(
            "color: #49627f; background: #f5f8fd; border: 1px solid #dce7f5; "
            "border-radius: 8px; padding: 8px 12px; font-weight: 700;"
        )
        upload_layout.addWidget(self.workflow_label)

        self.target_label = QLabel()
        self.target_label.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #244fbd; "
            "background: #f0f6ff; border: 1px solid #d5e4fb; border-radius: 7px; "
            "padding: 8px 12px;"
        )
        self.target_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        upload_layout.addWidget(self.target_label)
        self.import_status_label = QLabel("尚未选择文件")
        self.import_status_label.setStyleSheet(
            "background: #f5f7fb; color: #66758c; border: 1px solid #e0e7f0; "
            "border-radius: 7px; padding: 7px 11px; font-weight: 700;"
        )
        self.import_status_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.import_status_label.setMaximumWidth(760)
        self.import_status_label.setWordWrap(True)
        upload_layout.addWidget(self.import_status_label)
        self.hint = QPushButton("仅支持 Excel (.xlsx) 和 CSV (.csv) 文件\n点击此区域选择文件")
        self.hint.clicked.connect(self.choose_file)
        self.hint.setCursor(Qt.PointingHandCursor)
        self.hint.setFocusPolicy(Qt.NoFocus)
        self.hint.setMinimumHeight(104)
        self.hint.setStyleSheet("""
            QPushButton {
                background: #f6f9fe;
                border: 2px dashed #c9dcfa;
                border-radius: 10px;
                color: #627189;
                font-size: 15px;
                font-weight: bold;
                padding: 18px;
            }
            QPushButton:hover { background: #eef5ff; border-color: #8fb8f5; color: #315dd3; }
            QPushButton:pressed { background: #e4efff; }
        """)
        upload_layout.addWidget(self.hint)
        layout.addWidget(upload_panel)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setDocumentMode(True)
        self.workspace_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dbe6f3; border-radius: 10px; background: #ffffff; }
            QTabBar::tab { background: #eef4fb; color: #58708f; padding: 10px 18px; margin-right: 4px; border-radius: 7px; }
            QTabBar::tab:selected { background: #3f7dff; color: #ffffff; font-weight: 700; }
        """)
        self.result_panel, self.result_layout = make_panel("识别结果")
        self.workspace_tabs.addTab(self.result_panel, "识别预览")

        self.conflict_panel, self.conflict_layout = make_panel("数据预览 / 冲突")
        self.workspace_tabs.addTab(self.conflict_panel, "冲突与失败修正")

        self.result_pagination = PaginationBar(page_size=20)
        self.result_pagination.page_changed.connect(lambda _page: self._render_result_table())
        self.result_layout.addWidget(self.result_pagination)
        self.conflict_pagination = PaginationBar(page_size=20)
        self.conflict_pagination.page_changed.connect(lambda _page: self._render_conflict_table())
        self.conflict_layout.addWidget(self.conflict_pagination)

        self.history_panel, self.history_layout = make_panel("导入记录")
        self.workspace_tabs.addTab(self.history_panel, "导入历史")
        self.history_pagination = PaginationBar()
        self.history_pagination.page_changed.connect(lambda _page: self.refresh_history())
        self.history_layout.addWidget(self.history_pagination)
        self.raw_panel, self.raw_layout = make_panel("原始导入数据")
        self.workspace_tabs.addTab(self.raw_panel, "原始数据")
        self.raw_pagination = PaginationBar(page_size=20)
        self.raw_pagination.page_changed.connect(lambda _page: self.refresh_raw_rows())
        self.raw_layout.addWidget(self.raw_pagination)
        self.repair_panel, self.repair_layout = make_panel("失败记录修正历史")
        self.workspace_tabs.addTab(self.repair_panel, "修正历史")
        self.repair_pagination = PaginationBar(page_size=20)
        self.repair_pagination.page_changed.connect(lambda _page: self.refresh_repair_history())
        self.repair_layout.addWidget(self.repair_pagination)
        layout.addWidget(self.workspace_tabs)
        self._update_repair_controls()

        self.refresh_placeholder()
        self.refresh_history()
        self._update_target_label()

    def refresh_placeholder(self):
        self.workflow_label.setText("1 选择文件  →  2 检查识别结果  →  3 确认导入")
        self.result_rows = [["暂无文件", "-", "0", "0", "0", "0", "等待导入"]]
        self.conflict_rows = [["-", "-", "-", "-", "等待导入"]]
        self._render_result_table(["文件名称", "文件类型", "识别记录", "新增", "可合并", "冲突", "状态"])
        self._render_conflict_table(["IP", "字段", "原值", "新值", "建议操作"])
        self.raw_rows = []
        self.refresh_raw_rows()
        self.refresh_repair_history()

    def _render_result_table(self, headers=None):
        headers = headers or getattr(self, "result_headers", ["目标项目", "子表名称", "记录数", "新增", "已合并", "冲突", "错误", "状态"])
        self.result_headers = headers
        self.result_pagination.set_total(len(self.result_rows))
        start = (self.result_pagination.page - 1) * self.result_pagination.page_size
        self._set_panel_table(self.result_layout, headers, self.result_rows[start:start + self.result_pagination.page_size])

    def _render_conflict_table(self, headers=None):
        headers = headers or getattr(self, "conflict_headers", ["行号", "IP", "字段", "原值", "新值", "处理结果"])
        self.conflict_headers = headers
        self.conflict_pagination.set_total(len(self.conflict_rows))
        start = (self.conflict_pagination.page - 1) * self.conflict_pagination.page_size
        self._set_panel_table(self.conflict_layout, headers, self.conflict_rows[start:start + self.conflict_pagination.page_size])

    def _set_panel_table(self, layout, headers, rows):
        preserved = []
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                if isinstance(widget, PaginationBar):
                    preserved.append(widget)
                else:
                    widget.deleteLater()
        layout.addWidget(make_table(headers, rows))
        for widget in preserved:
            layout.addWidget(widget)

    def refresh_history(self):
        total, history = self.import_service.get_import_history(page=self.history_pagination.page, page_size=self.history_pagination.page_size)
        if self.history_pagination.set_total(total):
            total, history = self.import_service.get_import_history(
                page=self.history_pagination.page, page_size=self.history_pagination.page_size
            )
        rows = [
            [item["imported_at"], item["project"], item["file_name"], item["records"],
             item["new"], item["merge"], item["conflict"], item["status"]]
            for item in history
        ]
        self._set_panel_table(
            self.history_layout,
            ["导入时间", "目标项目", "文件名称", "记录数", "新增", "合并", "冲突", "状态"],
            rows or [["-", "暂无导入记录", "-", 0, 0, 0, 0, "-"]],
        )

    def refresh_raw_rows(self):
        headers = ["工作表", "行号"]
        for row in self.raw_rows:
            headers.extend(key for key in row if key not in headers)
        self.raw_pagination.set_total(len(self.raw_rows))
        start = (self.raw_pagination.page - 1) * self.raw_pagination.page_size
        rows = [[row.get(header, "") for header in headers] for row in
                self.raw_rows[start:start + self.raw_pagination.page_size]]
        self._set_panel_table(
            self.raw_layout, headers, rows or [["-", "-", "尚未读取原始数据"]],
        )

    def refresh_repair_history(self):
        self.repair_pagination.set_total(len(self.repair_history))
        start = (self.repair_pagination.page - 1) * self.repair_pagination.page_size
        rows = [[
            item.get("time", "-"), item.get("row", "-"),
            item.get("project_id", "-"), item.get("status", "-"),
            item.get("message", ""),
        ] for item in self.repair_history[start:start + self.repair_pagination.page_size]]
        self._set_panel_table(
            self.repair_layout,
            ["处理时间", "原始行号", "项目ID", "处理结果", "说明"],
            rows or [["-", "-", "-", "暂无修正记录", ""]],
        )

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择历史资料",
            "",
            "Excel / CSV Files (*.xlsx *.csv)",
        )
        if not file_path:
            return
        try:
            groups = self.import_service.read_file_groups(file_path)
            rows = [row for group in groups for row in group["rows"]]
            self.current_groups = groups
            self.current_rows = rows
            self.current_file_path = file_path
            self.raw_rows = []
            for group in groups:
                for preamble in group.get("preamble_rows", []):
                    self.raw_rows.append({
                        "工作表": group["sheet_name"],
                        "行号": preamble.get("行号", ""),
                        "行类型": "说明/表头",
                        **{key: value for key, value in preamble.items() if key != "行号"},
                    })
                for index, raw in enumerate(group.get("source_rows", []), start=1):
                    values = dict(raw) if isinstance(raw, dict) else {
                        f"列{column + 1}": value for column, value in enumerate(raw)
                    }
                    self.raw_rows.append({
                        "工作表": group["sheet_name"],
                        "行号": index + len(group.get("preamble_rows", [])),
                        "行类型": "数据",
                        **values,
                    })
            self.refresh_raw_rows()
            file_name = Path(file_path).name
            scanned_count = len(self.import_service.last_sheet_scan) or len(groups)
            is_multi_sheet = Path(file_path).suffix.lower() == ".xlsx" and scanned_count > 1
            self.auto_project_check.setEnabled(is_multi_sheet)
            self.auto_project_check.setChecked(is_multi_sheet)
            self._on_auto_project_changed(is_multi_sheet)
            self.hint.setText(
                f"{file_name}\n"
                f"扫描 {scanned_count} 个工作表，识别 {len(groups)} 个机器表，共 {len(rows)} 条记录\n"
                "点击此区域重新选择文件"
            )
            self.import_status_label.setText("文件已识别，尚未写入数据库，请点击右上方“确认导入”")
            self.workflow_label.setText(
                f"已完成 1/3：发现 {len(groups)} 个机器工作表、{len(rows)} 条记录，"
                "请检查识别结果后确认导入"
            )
            self.import_status_label.setStyleSheet(
                "background: #fff8e8; color: #8a5a00; border: 1px solid #f0d89a; "
                "border-radius: 6px; padding: 7px 10px; font-weight: 700;"
            )
            result_rows = [
                [file_name, item["sheet_name"], item["records"], item["status"]]
                for item in self.import_service.last_sheet_scan
            ] or [
                [file_name, group["sheet_name"], len(group["rows"]), "已识别，待导入"]
                for group in groups
            ]
            self.result_rows = result_rows
            self._render_result_table(["文件名称", "子表名称", "识别记录", "状态"])
            preview = [
                raw
                for group in groups
                for raw in group.get("source_rows", [])
            ][:5]
            if preview:
                headers = []
                for row in preview:
                    for key in row:
                        if key not in headers:
                            headers.append(key)
                table_rows = [[row.get(h, "") for h in headers] for row in preview]
                self.conflict_rows = table_rows or [["-"]]
                self._render_conflict_table(headers or ["字段"])
            else:
                self.refresh_placeholder()
            self._update_import_button()
            self.workspace_tabs.setCurrentIndex(0)
        except Exception as exc:
            show_toast(self, f"导入失败：{exc}", False)

    def refresh_projects(self):
        selected_id = self.project_box.currentData()
        self.project_box.clear()
        for project_id, project_name in self.project_service.get_project_options():
            self.project_box.addItem(display_project_name(project_name), project_id)
        index = self.project_box.findData(selected_id)
        if index >= 0:
            self.project_box.setCurrentIndex(index)

    def reload_data(self):
        self.project_box.blockSignals(True)
        self.refresh_projects()
        self.project_box.blockSignals(False)
        for pagination in (
            self.history_pagination, self.raw_pagination, self.repair_pagination,
            self.result_pagination, self.conflict_pagination,
        ):
            pagination.reset()
        self.refresh_history()
        self._update_import_button()

    def _update_import_button(self):
        auto_create = self.auto_project_check.isChecked() and self.auto_project_check.isEnabled()
        has_target = auto_create or bool(self.project_box.currentData())
        has_content = bool(self.current_rows) or any(
            group.get("source_rows") for group in getattr(self, "current_groups", [])
        )
        self.import_btn.setEnabled(has_content and has_target)
        self._update_target_label()

    def _on_auto_project_changed(self, checked: bool):
        self.project_box.setEnabled(not checked)
        self._update_import_button()

    def _update_target_label(self):
        if self.auto_project_check.isChecked() and self.auto_project_check.isEnabled():
            project_name = "按工作表自动创建项目"
        else:
            project_name = self.project_box.currentText() or "未选择项目"
        self.target_label.setText(f"导入目标项目：{project_name}")

    def import_current_file(self):
        groups = getattr(self, "current_groups", [])
        has_content = bool(self.current_rows) or any(group.get("source_rows") for group in groups)
        if not has_content or not self.current_file_path:
            show_toast(self, "请先选择文件", False)
            return
        try:
            self.import_btn.setEnabled(False)
            self.import_btn.setText("正在导入...")
            path = Path(self.current_file_path)
            groups = groups or [{"sheet_name": "默认工作表", "rows": self.current_rows,
                                 "source_rows": self.current_rows}]
            results = []
            for index, group in enumerate(groups):
                if self.auto_project_check.isChecked() and self.auto_project_check.isEnabled():
                    project_id = self.import_service.get_or_create_import_project(
                        group["sheet_name"], path.stem, index, group.get("project_metadata")
                    )
                else:
                    project_id = self.project_box.currentData()
                results.append((group, project_id, self.import_service.import_machines(
                    project_id=project_id,
                    rows=group["rows"],
                    source_rows=group.get("source_rows", group["rows"]),
                    sheet_name=group["sheet_name"],
                    file_name=path.name,
                    file_type=path.suffix.lower().lstrip("."),
                    file_size=path.stat().st_size,
                )))
            result = self.import_service.combine_results([item[2] for item in results])
            project_name = "、".join(
                self.import_service.get_project_label(project_id) for _group, project_id, _result in results
            )
            per_sheet_rows = []
            for group, project_id, sheet_result in results:
                per_sheet_rows.append([
                    display_project_name(self.import_service.get_project_label(project_id)),
                    group["sheet_name"],
                    sheet_result["records"],
                    sheet_result["new"],
                    sheet_result["merge"],
                    sheet_result["conflict"],
                    len(sheet_result["errors"]),
                    "已完成" if not sheet_result["errors"] else "部分完成",
                ])
            self.result_rows = per_sheet_rows
            self._render_result_table(["目标项目", "子表名称", "记录数", "新增", "已合并", "冲突", "错误", "状态"])
            conflict_rows = [
                [item["row"], item["ip"], item["field"], item["old"], item["new"], item["action"]]
                for item in result["conflicts"]
            ]
            error_rows = [[item["row"], "错误", "", item["message"], "", "未导入"] for item in result["errors"]]
            self.pending_errors = [error for _group, project_id, sheet_result in results for error in sheet_result["errors"]]
            self._update_repair_controls()
            self.conflict_rows = conflict_rows + error_rows or [["-", "-", "-", "-", "-", "无冲突"]]
            self._render_conflict_table(["行号", "IP", "字段", "原值", "新值", "处理结果"])
            self.workspace_tabs.setCurrentIndex(1 if result["errors"] or result["conflicts"] else 0)
            self.refresh_history()
            self.import_status_label.setText(
                f"导入完成：{len(results)} 个工作表，新增 {result['new']} 台，合并 {result['merge']} 台，"
                f"失败 {len(result['errors'])} 条"
            )
            self.workflow_label.setText(
                f"已完成 3/3：新增 {result['new']} 台，合并 {result['merge']} 台，"
                f"失败 {len(result['errors'])} 条"
            )
            self.import_status_label.setStyleSheet(
                "background: #eaf8f0; color: #17643a; border: 1px solid #a9dbbc; "
                "border-radius: 6px; padding: 7px 10px; font-weight: 700;"
            )
            self.import_completed.emit(0)
            show_toast(
                self,
                f"已导入 {project_name}：新增 {result['new']}，合并 {result['merge']}，冲突 {result['conflict']}",
            )
        except Exception as exc:
            self.workflow_label.setText("导入未完成：请根据错误提示修正文件后重新选择")
            self.import_status_label.setText(f"导入失败：{exc}")
            self.import_status_label.setStyleSheet(
                "background: #fff0f0; color: #9f2929; border: 1px solid #efb5b5; "
                "border-radius: 6px; padding: 7px 10px; font-weight: 700;"
            )
            show_toast(self, f"导入失败：{exc}", False)
        finally:
            self.import_btn.setText("确认导入")
            self._update_import_button()

    def fix_next_error(self):
        if not self.pending_errors:
            show_toast(self, "没有待修正的失败记录")
            return
        error = self.pending_errors[0]
        values = dict(error.get("data") or {})
        edits = {key: QLineEdit(str(value or "")) for key, value in values.items()}
        for edit in edits.values():
            edit.setMaxLength(200)
        fields = [(key, edit) for key, edit in edits.items()]
        dialog = FormDialog("修正导入失败记录", f"第 {error.get('row')} 行：{error.get('message')}", fields, columns=2, field_width=300, width=820, height=520, parent=self)
        dialog.save_button.setText("保存并重试")

        def retry():
            try:
                allowed = set(MACHINE_FIELD_LIMITS) | {"account"}
                row = {key: edit.text().strip() for key, edit in edits.items() if key in allowed or key == "ip"}
                self._retry_error(error, row)
                self.pending_errors.remove(error)
                self._record_repair(error, "已修正")
                self._save_repair_history()
                self._refresh_failed_error_views()
                self.workspace_tabs.setCurrentIndex(1)
                dialog.accept()
                show_toast(self, "失败记录已修正并写入机器信息")
            except Exception as exc:
                show_toast(dialog, f"修正失败：{exc}", False)

        dialog.save_button.clicked.connect(retry)
        dialog.exec()

    def _retry_error(self, error, row):
        """Write a repaired row using the same project/IP merge path as normal import."""
        payload = dict(row or {})
        ip = payload.pop("ip", "")
        if not ip:
            ip = next(
                (payload.get(field) for field in ("business_ip", "cluster_ip", "compute_ip", "storage_ip") if payload.get(field)),
                "",
            )
        ip = validate_ipv4(ip, "IP", required=True)
        return MachineService(self.current_user).merge_machine_data(error["project_id"], ip, payload)

    def _record_repair(self, error, status):
        self.repair_history.append({
            "time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "row": error.get("row"),
            "project_id": error.get("project_id"),
            "status": status,
            "message": error.get("message"),
        })

    def _refresh_failed_error_views(self):
        failed_rows = {error.get("row") for error in self.pending_errors}
        self.conflict_rows = [
            row for row in self.conflict_rows
            if not (len(row) >= 6 and row[1] == "错误" and row[0] not in failed_rows)
        ]
        if not self.conflict_rows:
            self.conflict_rows = [["-", "-", "-", "-", "-", "无冲突"]]
        self._render_conflict_table(["行号", "IP", "字段", "原值", "新值", "处理结果"])
        self._update_repair_controls()

    def _update_repair_controls(self):
        count = len(self.pending_errors)
        has_errors = count > 0
        self.fix_btn.setEnabled(has_errors)
        self.batch_fix_btn.setEnabled(has_errors)
        self.fix_btn.setVisible(has_errors)
        self.batch_fix_btn.setVisible(has_errors)
        self.workspace_tabs.setTabText(1, f"冲突与失败修正{f' ({count})' if has_errors else ''}")

    def _save_repair_history(self):
        QSettings("DeployMate", "DeployMate").setValue(
            "import_repair_history", json.dumps(self.repair_history[-200:], ensure_ascii=False)
        )
        if hasattr(self, "repair_pagination"):
            self.repair_pagination.page = 1
            self.refresh_repair_history()

    def batch_fix_errors(self):
        """Retry rows that already contain a usable IP, leaving invalid rows for editing."""
        if not self.pending_errors:
            return
        allowed = set(MACHINE_FIELD_LIMITS) | {"account"}
        remaining = []
        fixed = 0
        for error in self.pending_errors:
            row = {key: value for key, value in (error.get("data") or {}).items() if key in allowed or key == "ip"}
            try:
                self._retry_error(error, row)
                self._record_repair(error, "批量修正")
                fixed += 1
            except Exception:
                remaining.append(error)
        self.pending_errors = remaining
        self._save_repair_history()
        self._refresh_failed_error_views()
        self.workspace_tabs.setCurrentIndex(1)
        show_toast(self, f"批量重试完成：修正 {fixed} 条，剩余 {len(remaining)} 条需逐条编辑")
