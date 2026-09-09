from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter
from src.services.project_service import ProjectService
from src.services.machine_service import MachineService
from src.models import DailyReport, Expense, ImportFile, Machine, Project, get_session
from src.ui.widgets.common import make_button, make_page, make_panel, make_table

class StatusPieChart(QWidget):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.values = values
        self.setMinimumHeight(190)

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


class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.project_service = ProjectService()
        self.machine_service = MachineService()
        self.init_ui()
    
    def init_ui(self):
        page, layout, head = make_page("首页概览", "记录一次，自动复用。资料导入，自动合并。项目结束，一键导出。")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(page)
        head.addWidget(make_button("新建项目", True))
        
        # 统计卡片
        stats_layout = QGridLayout()
        stats_layout.setSpacing(14)
        
        stats = self.get_stats()
        
        cards = [
            (stats['total_projects'], "项目总数", f"进行中 {stats['ongoing']} · 已完成 {stats['completed']}"),
            (stats['total_machines'], "客户机器数量", "按 IP 自动识别和合并"),
            (stats['total_reports'], "SOP问题记录", "按项目持续维护"),
            (f"{stats['completeness']}%", "项目完整度", "自动检查项目、机器、SOP记录和费用"),
        ]
        
        for i, (num, label, note) in enumerate(cards):
            card = self.create_stat_card(num, label, note)
            stats_layout.addWidget(card, 0, i)
        
        stats_panel, stats_panel_layout = make_panel("工作台概览")
        stats_panel_layout.addLayout(stats_layout)
        layout.addWidget(stats_panel)

        chart_panel, chart_layout = make_panel("项目状态分布")
        chart_layout.addWidget(StatusPieChart([
            ("实施中", stats['ongoing'], "#3f7dff"),
            ("已完成", stats['completed'], "#2fbd87"),
            ("待开始 / 已归档", max(stats['total_projects'] - stats['ongoing'] - stats['completed'], 0), "#f0a52b"),
        ]))
        layout.addWidget(chart_panel)

        detail_row = QHBoxLayout()
        recent_panel, recent_layout = make_panel("最近项目")
        recent_layout.addWidget(make_table(["项目客户名称", "销售", "开始日期", "机器", "状态"], stats["recent_projects"]))
        detail_row.addWidget(recent_panel, 3)
        activity_panel, activity_layout = make_panel("数据概览")
        activity_layout.addWidget(QLabel(
            f"导入记录  {stats['import_count']} 条\n\nSOP问题记录  {stats['total_reports']} 条\n\n"
            f"费用总额  ¥{stats['expense_total']:.2f}\n\n完整度待补项目  {stats['incomplete_count']} 个"
        ))
        detail_row.addWidget(activity_panel, 2)
        layout.addLayout(detail_row)
        
        # 提示信息
        info_label = QLabel("当前使用本地 SQLite 数据库，程序关闭前会自动保存并执行备份。")
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
        
        title_label = QLabel(label)
        title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #627189; margin-top: 9px;")
        card_layout.addWidget(title_label)
        
        note_label = QLabel(note)
        note_label.setStyleSheet("font-size: 12px; color: #8794a8; margin-top: 9px;")
        card_layout.addWidget(note_label)
        
        card_layout.addStretch()
        
        return card
    
    def get_stats(self):
        """获取统计数据"""
        project_stats = self.project_service.get_project_stats()
        completeness = self.project_service.get_completeness()
        machine_count = self.machine_service.get_machine_count()
        
        session = get_session()
        try:
            report_count = session.query(DailyReport).count()
            expense_total = sum(float(row.amount or 0) for row in session.query(Expense).all())
            import_count = session.query(ImportFile).count()
            recent = session.query(Project).order_by(Project.created_at.desc()).limit(5).all()
        finally:
            session.close()
        return {
            'total_projects': project_stats['total'],
            'ongoing': project_stats['ongoing'],
            'completed': project_stats['completed'],
            'total_machines': machine_count,
            'total_reports': report_count,
            'expense_total': expense_total,
            'import_count': import_count,
            'completeness': completeness['average'],
            'incomplete_count': sum(item['score'] < 100 for item in completeness['projects']),
            'recent_projects': [[p.name, p.sales or "-", p.start_date or "-", session.query(Machine).filter(Machine.project_id == p.id).count(), p.status] for p in recent],
        }
