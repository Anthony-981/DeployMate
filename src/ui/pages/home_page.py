from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from datetime import datetime
from PySide6.QtCore import Qt, QPointF, QRectF, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from src.services.project_service import ProjectService
from src.services.user_service import UserService
from src.ui.widgets.common import make_button, make_page, make_panel, make_searchable_combo, make_table


class DashboardLoader(QThread):
    loaded = Signal(dict)
    failed = Signal(str)

    def __init__(self, current_user=None, owner_id=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.owner_id = owner_id

    def run(self):
        try:
            self.loaded.emit(ProjectService(self.current_user).get_dashboard_stats(self.owner_id))
        except Exception as exc:
            self.failed.emit(str(exc))

class StatusPieChart(QWidget):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.values = values
        self.setMinimumHeight(190)

    def set_values(self, values):
        self.values = values
        self.update()

    def paintEvent(self, _event):
        total = sum(value for _, value, _ in self.values) or 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.width() // 3
        diameter = min(150, self.height() - 20)
        rect = QRectF(center - diameter / 2, 10, diameter, diameter)
        start = 0
        for _label, value, color in self.values:
            span = int(360 * 16 * value / total)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawPie(rect, start, span)
            start += span
        y = 35
        painter.setPen(QColor("#24344f"))
        for label, value, color in self.values:
            painter.setBrush(QColor(color))
            painter.drawRect(self.width() // 2 + 15, y - 11, 12, 12)
            painter.drawText(self.width() // 2 + 35, y, f"{label}  {value} 个")
            y += 34


class DistributionPieChart(QWidget):
    COLORS = ["#3f7dff", "#2fbd87", "#f0a52b", "#e56b6f", "#8b6fe8", "#2aa7b8", "#6c7a89", "#d9822b"]

    def __init__(self, title, unit="个", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.values = []
        self.setMinimumHeight(290)

    def set_values(self, values):
        self.values = [
            (str(label), float(value or 0), self.COLORS[index % len(self.COLORS)])
            for index, (label, value) in enumerate(values)
            if float(value or 0) > 0
        ]
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#24344f"))
        painter.drawText(18, 24, self.title)
        if not self.values:
            painter.setPen(QColor("#8794a8"))
            painter.drawText(18, 65, "暂无数据")
            return
        total = sum(value for _, value, _ in self.values)
        diameter = min(150, self.height() - 60)
        rect = QRectF(24, 42, diameter, diameter)
        start = 0
        for _label, value, color in self.values:
            span = int(360 * 16 * value / total)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawPie(rect, start, span)
            start += span
        y = 58
        painter.setPen(QColor("#24344f"))
        for label, value, color in self.values:
            painter.setBrush(QColor(color))
            painter.drawRect(diameter + 48, y - 10, 11, 11)
            painter.drawText(diameter + 67, y, f"{label}  {value:g} {self.unit}")
            y += 29


class TrendLineChart(QWidget):
    COLORS = ["#3f7dff", "#2fbd87", "#8b6fe8"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.setMinimumHeight(290)

    def set_values(self, values):
        self.values = values or []
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#24344f"))
        painter.drawText(18, 24, "近 7 天数据趋势")
        if not self.values:
            painter.setPen(QColor("#8794a8"))
            painter.drawText(18, 65, "暂无趋势数据")
            painter.end()
            return
        left, top, width, height = 42, 58, max(260, self.width() - 68), 165
        keys = ("项目数", "机器数", "导入文件数")
        maximum = max(
            1.0,
            max(float(item.get(key, 0) or 0) for item in self.values for key in keys),
        )
        painter.setPen(QColor("#dfe8f5"))
        for step in range(5):
            y = top + height - height * step / 4
            painter.drawLine(left, int(y), left + width, int(y))
            painter.setPen(QColor("#71829b"))
            painter.drawText(8, int(y + 4), str(int(maximum * step / 4)))
            painter.setPen(QColor("#dfe8f5"))
        for key_index, key in enumerate(keys):
            points = []
            for index, item in enumerate(self.values):
                x = left + width * index / max(len(self.values) - 1, 1)
                value = float(item.get(key, 0) or 0)
                y = top + height - height * value / maximum
                points.append(QPointF(x, y))
            painter.setPen(QColor(self.COLORS[key_index]))
            for first, second in zip(points, points[1:]):
                painter.drawLine(first, second)
            painter.setBrush(QColor(self.COLORS[key_index]))
            for point in points:
                painter.drawEllipse(point, 4, 4)
            painter.setPen(QColor(self.COLORS[key_index]))
            painter.drawEllipse(self.width() - 210 + key_index * 74, 12, 9, 9)
            painter.drawText(self.width() - 195 + key_index * 74, 21, key)
        painter.setPen(QColor("#687892"))
        for index, item in enumerate(self.values):
            x = left + width * index / max(len(self.values) - 1, 1)
            painter.drawText(int(x - 18), top + height + 24, str(item.get("日期", "")))
        painter.end()


class CompletenessBars(QWidget):
    COLORS = ["#2fbd87", "#3f7dff", "#f0a52b", "#e56b6f"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.setMinimumHeight(290)

    def set_values(self, values):
        self.values = [(str(label), int(value or 0)) for label, value in values]
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#24344f"))
        painter.drawText(18, 24, "项目完整度分布")
        maximum = max([value for _, value in self.values] or [1])
        for index, (label, value) in enumerate(self.values):
            y = 60 + index * 48
            painter.setPen(QColor("#687892"))
            painter.drawText(18, y + 16, label)
            track = QRectF(95, y + 3, max(180, self.width() - 185), 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#edf2f8"))
            painter.drawRoundedRect(track, 9, 9)
            fill = QRectF(track.left(), track.top(), track.width() * value / maximum if maximum else 0, track.height())
            painter.setBrush(QColor(self.COLORS[index % len(self.COLORS)]))
            painter.drawRoundedRect(fill, 9, 9)
            painter.setPen(QColor("#24344f"))
            painter.drawText(int(track.right() + 12), y + 17, f"{value} 个")


class HomePage(QWidget):
    def __init__(self, current_user=None):
        super().__init__()
        self.current_user = current_user
        self.project_service = ProjectService(current_user)
        self.user_service = UserService()
        self.is_admin = self.user_service.is_admin(current_user)
        self.loader = None
        self._pending_reload = False
        self.init_ui()
        QTimer.singleShot(0, self.reload_data)
    
    def init_ui(self):
        page, layout, head = make_page("欢迎使用 DeployMate", "实施信息台账，让项目数据更有条理。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)
        if self.is_admin:
            user_label = QLabel("用户筛选：")
            user_label.setStyleSheet("font-weight: 700; color: #425069;")
            self.user_filter = make_searchable_combo(QComboBox())
            self.user_filter.setMinimumWidth(260)
            self.user_filter.setMaximumWidth(360)
            head.addWidget(user_label)
            head.addWidget(self.user_filter)
            self.refresh_users()
            self.user_filter.currentIndexChanged.connect(self.reload_data)

        welcome = QFrame()
        welcome.setObjectName("welcomeBanner")
        welcome.setStyleSheet("""
            QFrame#welcomeBanner {
                background: #eaf3ff;
                border: 1px solid #cfe1fb;
                border-radius: 10px;
            }
        """)
        welcome_layout = QHBoxLayout(welcome)
        welcome_layout.setContentsMargins(22, 18, 22, 18)
        welcome_copy = QVBoxLayout()
        welcome_title = QLabel("实施信息台账")
        welcome_title.setStyleSheet("font-size: 22px; font-weight: 900; color: #17417e;")
        welcome_copy.addWidget(welcome_title)
        welcome_subtitle = QLabel("项目数据集中管理，年终汇报快速掌握进度、资源与利润。")
        welcome_subtitle.setStyleSheet("font-size: 14px; color: #56749e;")
        welcome_copy.addWidget(welcome_subtitle)
        welcome_layout.addLayout(welcome_copy)
        welcome_layout.addStretch()
        welcome_mark = QLabel("项目  ·  机器  ·  资料  ·  费用")
        welcome_mark.setStyleSheet("color: #3d79d9; font-weight: 800; padding-right: 12px;")
        welcome_layout.addWidget(welcome_mark)
        layout.addWidget(welcome)
        
        # 统计卡片
        stats_layout = QGridLayout()
        stats_layout.setSpacing(14)
        
        cards = [
            ("项目总数", "较上月变化"),
            ("机器总数", "按 IP 自动识别和合并"),
            ("导入 Excel 文件", "资料导入次数"),
            ("实际利润", "考核费用减去出差费用"),
        ]
        self.stat_values = []
        self.stat_notes = []
        for i, (label, note) in enumerate(cards):
            card = self.create_stat_card("…", label, note)
            stats_layout.addWidget(card, 0, i)
        
        stats_panel = QFrame()
        stats_panel.setObjectName("statsPanel")
        stats_panel.setStyleSheet("QFrame#statsPanel { background: transparent; border: none; }")
        stats_panel_layout = QVBoxLayout(stats_panel)
        stats_panel_layout.setContentsMargins(0, 0, 0, 0)
        stats_panel_layout.addLayout(stats_layout)
        layout.addWidget(stats_panel)

        analysis_row = QHBoxLayout()
        status_panel, status_layout = make_panel("项目状态分布")
        self.status_chart = DistributionPieChart("项目状态", "个")
        status_layout.addWidget(self.status_chart)
        analysis_row.addWidget(status_panel, 1)

        trend_panel, trend_layout = make_panel("近 7 天数据趋势")
        self.trend_chart = TrendLineChart()
        trend_layout.addWidget(self.trend_chart)
        analysis_row.addWidget(trend_panel, 1)

        activity_panel, self.activity_layout = make_panel("最近动态")
        self.activity_table = make_table(["类型", "内容", "时间"], [])
        self.activity_layout.addWidget(self.activity_table)
        analysis_row.addWidget(activity_panel, 1)
        layout.addLayout(analysis_row)

        detail_row = QHBoxLayout()
        recent_panel, self.recent_layout = make_panel("最近项目")
        self.recent_table = make_table(["项目名称", "客户名称", "机器数量", "创建时间", "状态"], [])
        self.recent_layout.addWidget(self.recent_table)
        detail_row.addWidget(recent_panel, 1)

        machine_panel, self.machine_layout = make_panel("机器信息统计")
        self.machine_table = make_table(["IP地址", "主机名", "操作系统", "显卡", "状态"], [])
        self.machine_layout.addWidget(self.machine_table)
        detail_row.addWidget(machine_panel, 1)
        layout.addLayout(detail_row)

        self.user_panel, self.user_layout = make_panel("用户数据概览")
        self.user_table = make_table(
            ["用户", "角色", "状态", "项目数", "机器数", "导入次数", "考核费用", "出差费用", "实际利润"],
            [],
        )
        self.user_layout.addWidget(self.user_table)
        self.user_panel.setVisible(False)
        layout.addWidget(self.user_panel)
        
        # 提示信息
        info_label = QLabel("本地数据已保存到 SQLite 数据库，备份策略可在设置页面调整。")
        info_label.setStyleSheet("""
            background: #eaf2ff;
            color: #2d5bff;
            padding: 14px;
            border-radius: 12px;
            font-size: 14px;
        """)
        layout.addWidget(info_label)
        
        layout.addStretch()
    
    def create_stat_card(self, num, label, note):
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dfe8f5;
                border-radius: 18px;
                padding: 17px;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        
        num_label = QLabel(str(num))
        num_label.setStyleSheet("font-size: 30px; font-weight: 900; color: #0f1f3a;")
        card_layout.addWidget(num_label)
        self.stat_values.append(num_label)
        
        title_label = QLabel(label)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #627189; margin-top: 9px;")
        card_layout.addWidget(title_label)
        
        note_label = QLabel(note)
        note_label.setStyleSheet("font-size: 12px; color: #8794a8; margin-top: 9px;")
        card_layout.addWidget(note_label)
        self.stat_notes.append(note_label)
        
        card_layout.addStretch()
        
        return card
    
    def reload_data(self):
        if self.loader and self.loader.isRunning():
            self._pending_reload = True
            return
        self.loader = DashboardLoader(self.current_user, self._selected_owner_id(), self)
        self.loader.loaded.connect(self.apply_stats)
        self.loader.failed.connect(self.show_load_error)
        self.loader.start()

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

    def apply_stats(self, stats):
        values = [
            stats["total_projects"], stats["total_machines"], stats["import_count"],
            f'¥{stats["profit_total"]:.2f}',
        ]
        for label, value in zip(self.stat_values, values):
            label.setText(str(value))
        self.stat_notes[0].setText(f'实施中 {stats["ongoing"]} · 已完成 {stats["completed"]}')
        self.stat_notes[1].setText(f'较上月 +{stats["total_machines"]}')
        self.stat_notes[2].setText(f'累计导入 {stats["import_count"]} 次')
        self.stat_notes[3].setText(
            f'考核 ¥{stats["assessment_fee_total"]:.2f} - 成本 ¥{stats["actual_cost_total"]:.2f}'
        )
        self.status_chart.set_values(stats["status_distribution"])
        self.trend_chart.set_values(stats.get("daily_trend", []))
        self.recent_layout.removeWidget(self.recent_table)
        self.recent_table.deleteLater()
        self.recent_table = make_table(
            ["项目名称", "客户名称", "机器数量", "创建时间", "状态"], stats["recent_projects"]
        )
        self.recent_layout.addWidget(self.recent_table)
        self.activity_layout.removeWidget(self.activity_table)
        self.activity_table.deleteLater()
        self.activity_table = make_table(["类型", "内容", "时间"], stats.get("recent_activities", []))
        self.activity_layout.addWidget(self.activity_table)
        self.machine_layout.removeWidget(self.machine_table)
        self.machine_table.deleteLater()
        self.machine_table = make_table(
            ["IP地址", "主机名", "操作系统", "显卡", "状态"],
            stats.get("recent_machines", []),
        )
        self.machine_layout.addWidget(self.machine_table)
        self.user_panel.setVisible(bool(stats.get("user_summaries")))
        self.user_layout.removeWidget(self.user_table)
        self.user_table.deleteLater()
        self.user_table = make_table(
            ["用户", "角色", "状态", "项目数", "机器数", "导入次数", "考核费用", "出差费用", "实际利润"],
            stats.get("user_summaries", []),
        )
        self.user_layout.addWidget(self.user_table)
        if self._pending_reload:
            self._pending_reload = False
            QTimer.singleShot(0, self.reload_data)

    def show_load_error(self, message):
        self.activity_layout.removeWidget(self.activity_table)
        self.activity_table.deleteLater()
        self.activity_table = make_table(
            ["类型", "内容", "时间"],
            [["加载失败", str(message), "-"]],
        )
        self.activity_layout.addWidget(self.activity_table)
