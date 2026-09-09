from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from src.ui.widgets.common import APP_STYLESHEET, show_toast


class NetworkMappingDialog(QDialog):
    NETWORK_TYPES = ["不保存", "管理网", "业务网", "集群网", "存储网", "计算网"]

    def __init__(self, interfaces: list[dict], connection_host: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle("选择网卡网络类型")
        self.setMinimumSize(760, 420)
        layout = QVBoxLayout(self)
        title = QLabel("为每个网络接口选择用途。每种网络类型只能选择一个接口。")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0f1f3a;")
        layout.addWidget(title)

        self.table = QTableWidget(len(interfaces), 4)
        self.table.setHorizontalHeaderLabels(["网卡名称", "IPv4 地址", "前缀长度", "网络类型"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.combos = []
        for row, interface in enumerate(interfaces):
            self.table.setItem(row, 0, QTableWidgetItem(interface["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(interface["ip"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(interface["prefix"])))
            combo = QComboBox()
            combo.setFocusPolicy(Qt.NoFocus)
            combo.addItems(self.NETWORK_TYPES)
            if interface["ip"] == connection_host:
                combo.setCurrentText("管理网")
            self.table.setCellWidget(row, 3, combo)
            self.combos.append(combo)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存网络映射")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        selected = [combo.currentText() for combo in self.combos if combo.currentText() != "不保存"]
        duplicates = sorted({name for name in selected if selected.count(name) > 1})
        if duplicates:
            show_toast(self, f"每种网络只能选择一个接口：{', '.join(duplicates)}", False)
            return
        if "管理网" not in selected:
            show_toast(self, "请至少选择一个管理网接口", False)
            return
        if "业务网" not in selected and "集群网" not in selected:
            show_toast(self, "业务网或集群网至少选择一个", False)
            return
        self.accept()

    def mappings(self) -> dict[str, str]:
        field_map = {"管理网": "ip", "业务网": "business_ip", "集群网": "cluster_ip", "存储网": "storage_ip", "计算网": "compute_ip"}
        result = {}
        for row, combo in enumerate(self.combos):
            field = field_map.get(combo.currentText())
            if field:
                result[field] = self.table.item(row, 1).text()
        return result
