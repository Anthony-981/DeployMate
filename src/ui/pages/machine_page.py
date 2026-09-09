from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QHBoxLayout, QVBoxLayout, QWidget

from src.services.machine_service import MachineService
from src.services.project_service import ProjectService
from src.services.ssh_service import SSHService
from src.ui.dialogs.network_mapping_dialog import NetworkMappingDialog
from src.ui.widgets.common import (
    FormDialog,
    add_table_actions,
    confirm_action,
    filter_table,
    make_button,
    make_management_toolbar,
    make_page,
    make_panel,
    make_table,
    show_toast,
    selected_record_ids,
    PasswordLineEdit,
    PasswordCellWidget,
    make_searchable_combo,
    PaginationBar,
    display_project_name,
)
from src.utils.validators import MACHINE_FIELD_LIMITS


IP_REGEX = QRegularExpression(
    r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})?$"
)


class MachinePage(QWidget):
    def __init__(self):
        super().__init__()
        self.project_service = ProjectService()
        self.machine_service = MachineService()
        self.ssh_service = SSHService()
        self.build_ui()

    def build_ui(self):
        page, layout, _head = make_page("机器信息", "按项目维护服务器网络、账号、GPU 和系统信息。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)

        scope_panel, scope_layout = make_panel("项目工作区")
        scope_row = QHBoxLayout()
        scope_row.setSpacing(12)
        self.project_filter = make_searchable_combo(QComboBox())
        self.project_filter.setMinimumWidth(380)
        self.project_filter.setMaximumWidth(520)
        self.project_filter.setPlaceholderText("输入项目名称搜索")
        filter_label = QLabel("当前项目")
        filter_label.setStyleSheet("font-weight: 700; color: #425069;")
        scope_row.addWidget(filter_label)
        scope_row.addWidget(self.project_filter)
        self.project_summary = QLabel("全部项目 · 正在统计机器数量")
        self.project_summary.setMinimumWidth(300)
        self.project_summary.setStyleSheet(
            "color: #5c6f8e; background: #f4f7fc; border: 1px solid #dce6f3; "
            "border-radius: 8px; padding: 7px 12px; font-weight: 700;"
        )
        scope_row.addWidget(self.project_summary)
        scope_row.addStretch()
        scope_layout.addLayout(scope_row)
        scope_hint = QLabel("选择一个项目后，列表只显示该项目的机器；选择“全部项目”可查看汇总清单。")
        scope_hint.setStyleSheet("color: #72819a; padding: 5px 0 0 72px;")
        scope_layout.addWidget(scope_hint)
        layout.addWidget(scope_panel)

        panel, panel_layout = make_panel("机器清单")
        toolbar, self.search_edit, refresh_btn, edit_btn, delete_btn, add_btn = make_management_toolbar("添加机器")
        refresh_btn.clicked.connect(self.reload_data)
        edit_btn.clicked.connect(self.edit_selected_machine)
        delete_btn.clicked.connect(self.delete_selected_machine)
        add_btn.clicked.connect(lambda: self.open_machine_dialog())
        delete_all_btn = make_button("一键删除")
        delete_all_btn.setToolTip("删除当前项目或搜索范围内的全部机器")
        delete_all_btn.clicked.connect(self.delete_all_machines)
        toolbar.insertWidget(toolbar.count() - 1, delete_all_btn)
        ssh_btn = make_button("SSH 自动采集")
        ssh_btn.clicked.connect(self.collect_by_ssh)
        toolbar.insertWidget(toolbar.count() - 1, ssh_btn)
        self.search_edit.textChanged.connect(self.search_all_fields)
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

    def select_project(self, project_id: int):
        self.refresh_projects()
        index = self.project_filter.findData(project_id)
        self.project_filter.setCurrentIndex(index if index >= 0 else 0)
        self.refresh_table()

    def refresh_table(self):
        if hasattr(self, "machine_table"):
            self.list_layout.removeWidget(self.machine_table)
            self.machine_table.deleteLater()
        project_id = self.project_filter.currentData()
        total, machines = self.machine_service.get_machines_page(
            self.pagination.page, self.pagination.page_size, project_id, self.search_edit.text()
        )
        self.pagination.set_total(total)
        selected_name = self.project_filter.currentText().strip() or "全部项目"
        self.project_summary.setText(f"{selected_name} · 当前显示 {total} 台机器")
        project_labels = {project.id: display_project_name(project.name) for project in self.project_service.get_all_projects()}
        rows = [[
            m.id, "", project_labels.get(m.project_id, "-"), m.role, m.ip, m.business_ip,
            m.cluster_ip, m.compute_ip, m.storage_ip,
            m.username or m.account, "", m.gpu_count, m.gpu_model,
            m.gpu_interconnect, m.hostname, m.os, m.cpu, m.memory, m.gpu, m.cuda, m.docker,
        ] for m in machines]
        self.machine_table = make_table(
            ["ID", "操作", "所属项目", "角色", "管理网IP", "业务网IP", "集群网IP", "计算网IP", "存储网IP",
             "用户名", "密码", "GPU数量", "GPU型号", "GPU互联", "主机名", "OS", "CPU",
             "内存", "GPU", "CUDA", "Docker"],
            rows,
        )
        self.machine_table.setColumnHidden(0, True)
        password_column = 10
        for row, machine in enumerate(machines):
            self.machine_table.setCellWidget(row, password_column, PasswordCellWidget(machine.password))
        if machines:
            password_width = max(
                150,
                max(len(str(machine.password or "")) * 12 + 108 for machine in machines),
            )
            self.machine_table.setColumnWidth(password_column, password_width)
        add_table_actions(
            self.machine_table, [machine.id for machine in machines], self.edit_machine, self.delete_machine
        )
        self.machine_table.cellDoubleClicked.connect(lambda _row, _column: self.edit_selected_machine())
        self.list_layout.insertWidget(self.list_layout.count() - 1, self.machine_table, 1)

    def search_all_fields(self):
        self.pagination.page = 1
        self.refresh_table()

    def _selected_machine_id(self):
        row = self.machine_table.currentRow()
        item = self.machine_table.item(row, 0) if row >= 0 else None
        return int(item.text()) if item else None

    def _make_machine_fields(self, machine=None, prefill=None):
        prefill = prefill or {}
        project_box = make_searchable_combo(QComboBox())
        for project in self.project_service.get_all_projects():
            project_box.addItem(display_project_name(project.name), project.id)
        selected_project = machine.project_id if machine else (prefill.get("project_id") or self.project_filter.currentData())
        index = project_box.findData(selected_project)
        if index >= 0:
            project_box.setCurrentIndex(index)

        names = [
            "role", "ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip", "username",
            "password", "gpu_count", "gpu_model", "gpu_interconnect", "hostname", "os", "cpu",
            "memory", "gpu", "cuda", "docker",
        ]
        edits = {
            name: PasswordLineEdit(str(prefill.get(name, getattr(machine, name, "") if machine else "") or ""))
            if name == "password" else QLineEdit(str(prefill.get(name, getattr(machine, name, "") if machine else "") or ""))
            for name in names
        }
        for name, edit in edits.items():
            edit.setMaxLength(MACHINE_FIELD_LIMITS.get(name, 100))
        for name in ("ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip"):
            edits[name].setValidator(QRegularExpressionValidator(IP_REGEX, self))
        edits["gpu_count"].setValidator(QIntValidator(0, 999999999, self))
        edits["ip"].setPlaceholderText("例如：10.10.10.20")
        return project_box, edits

    def open_machine_dialog(self, machine=None, prefill=None):
        project_box, edits = self._make_machine_fields(machine, prefill)
        fields = [
            ("项目 *", project_box), ("角色", edits["role"]), ("管理网IP *", edits["ip"]),
            ("业务网IP（至少一项）", edits["business_ip"]),
            ("集群网IP（至少一项）", edits["cluster_ip"]),
            ("计算网IP", edits["compute_ip"]), ("存储网IP", edits["storage_ip"]),
            ("用户名", edits["username"]), ("密码", edits["password"]),
            ("GPU数量", edits["gpu_count"]), ("GPU型号", edits["gpu_model"]),
            ("GPU互联", edits["gpu_interconnect"]), ("主机名", edits["hostname"]),
            ("OS", edits["os"]), ("CPU", edits["cpu"]), ("内存", edits["memory"]),
            ("GPU", edits["gpu"]), ("CUDA", edits["cuda"]), ("Docker", edits["docker"]),
        ]
        dialog = FormDialog(
            "编辑机器" if machine else "添加机器",
            "管理网 IP 为机器唯一标识，业务网 IP 或集群网 IP 至少填写一个。",
            fields, columns=3, field_width=280, width=1120, height=680, parent=self,
        )
        def save():
            payload = {key: edit.text().strip() for key, edit in edits.items() if key != "ip"}
            payload["account"] = payload["username"]
            try:
                if machine:
                    self.machine_service.update_machine(
                        machine.id, project_id=project_box.currentData(), ip=edits["ip"].text().strip(), **payload
                    )
                else:
                    self.machine_service.create_machine(
                        project_id=project_box.currentData(), ip=edits["ip"].text().strip(), **payload
                    )
                dialog.accept()
                self.select_project(project_box.currentData())
                show_toast(self, "机器已更新" if machine else "机器已添加")
            except Exception as exc:
                show_toast(dialog, str(exc), False)

        dialog.save_button.setText("更新" if machine else "添加")
        dialog.save_button.clicked.connect(save)
        dialog.exec()

    def edit_selected_machine(self):
        machine_id = self._selected_machine_id()
        if not machine_id:
            show_toast(self, "请先选择需要编辑的机器", False)
            return
        self.edit_machine(machine_id)

    def edit_machine(self, machine_id):
        machine = self.machine_service.get_machine_by_id(machine_id)
        if machine:
            self.open_machine_dialog(machine)

    def delete_selected_machine(self):
        machine_ids = selected_record_ids(self.machine_table)
        if not machine_ids:
            show_toast(self, "请先选择需要删除的机器", False)
            return
        if len(machine_ids) == 1:
            self.delete_machine(machine_ids[0])
            return
        if confirm_action(self, "确认批量删除", f"确定删除选中的 {len(machine_ids)} 台机器吗？"):
            for machine_id in machine_ids:
                self.machine_service.delete_machine(machine_id)
            self.refresh_table()
            show_toast(self, f"已删除 {len(machine_ids)} 台机器")

    def delete_all_machines(self):
        project_id = self.project_filter.currentData()
        total, _ = self.machine_service.get_machines_page(
            1, 1, project_id, self.search_edit.text()
        )
        if not total:
            show_toast(self, "当前范围没有可删除的机器")
            return
        scope = self.project_filter.currentText().strip() or "全部项目"
        if not confirm_action(
            self, "确认一键删除",
            f"确定删除“{scope}”下当前搜索范围内的全部 {total} 台机器吗？\n此操作不可恢复。"
        ):
            return
        try:
            removed = self.machine_service.delete_all_machines(project_id, self.search_edit.text())
        except Exception as exc:
            show_toast(self, f"删除失败：{exc}", False)
            return
        self.pagination.page = 1
        self.refresh_table()
        pages = getattr(self.window(), "pages", [])
        if pages and pages[0] is not None:
            reload_home = getattr(pages[0], "reload_data", None)
            if callable(reload_home):
                reload_home()
        show_toast(self, f"已一键删除 {removed} 台机器")

    def delete_machine(self, machine_id):
        machine = self.machine_service.get_machine_by_id(machine_id)
        if not machine:
            self.refresh_table()
            return
        if confirm_action(self, "确认删除", f"确定删除机器 {machine.ip} 吗？"):
            self.machine_service.delete_machine(machine_id)
            self.refresh_table()
            show_toast(self, "机器已删除")

    def collect_by_ssh(self):
        project_box = make_searchable_combo(QComboBox())
        for project in self.project_service.get_all_projects():
            project_box.addItem(display_project_name(project.name), project.id)
        current_project = self.project_filter.currentData()
        if current_project:
            project_box.setCurrentIndex(project_box.findData(current_project))
        host_edit = QLineEdit()
        host_edit.setPlaceholderText("服务器 IP 或主机名")
        port_edit = QLineEdit("22")
        port_edit.setValidator(QIntValidator(1, 65535, port_edit))
        username_edit = QLineEdit()
        username_edit.setPlaceholderText("例如：root")
        password_edit = PasswordLineEdit()
        password_edit.setPlaceholderText("SSH 登录密码")
        connection_dialog = FormDialog(
            "SSH 自动采集",
            "先选择所属项目，再输入 SSH 地址。采集完成后会打开机器录入页供确认保存。",
            [("所属项目 *", project_box), ("SSH 地址 *", host_edit), ("端口 *", port_edit), ("用户名 *", username_edit), ("密码 *", password_edit)],
            columns=2, field_width=300, width=760, height=410, parent=self,
        )
        connection_dialog.save_button.setText("开始采集")

        def run_collection():
            host, username, password = host_edit.text().strip(), username_edit.text().strip(), password_edit.text()
            if not project_box.currentData():
                show_toast(connection_dialog, "请选择 SSH 采集结果所属的项目", False)
                return
            if not host or not port_edit.text() or not username or not password:
                show_toast(connection_dialog, "SSH 地址、端口、用户名和密码均不能为空", False)
                return
            connection_dialog.save_button.setEnabled(False)
            connection_dialog.save_button.setText("采集中...")
            QApplication.processEvents()
            try:
                info = self.ssh_service.collect_server_info(
                    host=host, username=username, password=password, port=int(port_edit.text())
                )
                interfaces = info.pop("interfaces", [])
                if not interfaces:
                    raise ValueError("服务器未返回可用的 IPv4 网卡信息")
                mapping_dialog = NetworkMappingDialog(interfaces, host, connection_dialog)
                if not mapping_dialog.exec():
                    return
                connection_dialog.accept()
                self.open_machine_dialog(prefill={**info, "project_id": project_box.currentData(), "username": username, "password": password, **mapping_dialog.mappings()})
            except Exception as exc:
                show_toast(connection_dialog, f"SSH采集失败：{exc}", False)
            finally:
                connection_dialog.save_button.setEnabled(True)
                connection_dialog.save_button.setText("开始采集")

        connection_dialog.save_button.clicked.connect(run_collection)
        connection_dialog.exec()
