from datetime import date, datetime, timedelta

from src.models import DailyReport, Expense, ImportFile, Machine, Project, get_session
from src.services.db_service import DatabaseService
from src.services.machine_service import MachineService
from src.services.project_service import ProjectService


def test_dashboard_and_paged_queries_with_large_dataset(tmp_path):
    db_path = tmp_path / "performance.db"
    DatabaseService(str(db_path))

    session = get_session()
    try:
        projects = [
            Project(
                name=f"性能项目{i:04d}",
                customer=f"客户{i % 20}",
                project_code=f"PERF-{i:04d}",
                status=("实施中" if i % 4 == 0 else "已完成" if i % 4 == 1 else "待开始"),
                created_at=datetime(2026, 1, 1) + timedelta(seconds=i),
            )
            for i in range(500)
        ]
        session.add_all(projects)
        session.flush()
        project_ids = [project.id for project in projects]
        session.add_all([
            Machine(project_id=project_ids[i % len(project_ids)], ip=f"10.0.{i // 255}.{i % 255 + 1}")
            for i in range(5000)
        ])
        session.add_all([
            DailyReport(
                project_id=project_ids[i % len(project_ids)],
                report_date=date(2026, 1, 1) + timedelta(days=i // len(project_ids)),
                work_content=f"问题记录{i}",
            )
            for i in range(5000)
        ])
        session.add_all([
            Expense(
                project_id=project_ids[i % len(project_ids)],
                expense_date=date(2026, 1, (i % 28) + 1),
                expense_type="交通",
                amount="10.00",
            )
            for i in range(5000)
        ])
        session.add_all([
            ImportFile(
                project_id=project_ids[i % len(project_ids)],
                file_name=f"import-{i}.xlsx",
                records_count=1,
            )
            for i in range(500)
        ])
        session.commit()
    finally:
        session.close()

    stats = ProjectService().get_dashboard_stats()
    assert stats["total_projects"] == 500
    assert stats["total_machines"] == 5000
    assert stats["total_reports"] == 5000
    assert stats["import_count"] == 500
    assert len(stats["recent_projects"]) == 5

    total, rows = MachineService().get_machines_page(page=1, page_size=20)
    assert total == 5000
    assert len(rows) == 20
    assert rows[0][0].project_id > 0
    assert isinstance(rows[0][1], str)
