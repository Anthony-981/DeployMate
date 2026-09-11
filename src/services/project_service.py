from typing import List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy import case, cast, func, or_, String
from src.models import Project, Machine, DailyReport, Expense, ImportFile, ImportRow, User, get_session
from src.services.access_service import owner_id_for, scope_query
from src.services.user_service import UserService
from src.services.expense_service import ExpenseService
from src.utils.validators import (
    PROJECT_FIELD_LIMITS,
    ValidationError,
    clean_text,
    optional_text,
    require_text,
    validate_choice,
    validate_date_range,
)

class ProjectService:
    def __init__(self, current_user=None):
        self.current_user = current_user

    def _query(self, session):
        return scope_query(session.query(Project), Project, self.current_user)
    
    def get_all_projects(self) -> List[Project]:
        """获取所有项目"""
        session = get_session()
        try:
            return self._query(session).order_by(Project.created_at.desc()).all()
        finally:
            session.close()

    def _filter_owner_for_admin(self, query, owner_id=None):
        if owner_id and UserService.is_admin(self.current_user):
            return query.filter(Project.owner_id == int(owner_id))
        return query

    def get_project_options(self, owner_id=None) -> list[tuple[int, str]]:
        """Return lightweight project choices for combo boxes."""
        session = get_session()
        try:
            query = self._filter_owner_for_admin(self._query(session), owner_id)
            return query.with_entities(Project.id, Project.name).order_by(Project.created_at.desc()).all()
        finally:
            session.close()

    def get_project_label_map(self, project_ids: list[int] | None = None) -> dict[int, str]:
        session = get_session()
        try:
            query = self._query(session).with_entities(Project.id, Project.name)
            if project_ids:
                query = query.filter(Project.id.in_(set(project_ids)))
            return {project_id: name for project_id, name in query.all()}
        finally:
            session.close()

    def get_projects_page(self, page=1, page_size=20, search="", owner_id=None):
        session = get_session()
        try:
            query = self._filter_owner_for_admin(self._query(session), owner_id)
            keyword = (search or "").strip()
            if keyword:
                pattern = f"%{keyword}%"
                query = query.filter(or_(
                    Project.name.ilike(pattern),
                    Project.customer.ilike(pattern),
                    Project.project_code.ilike(pattern),
                    Project.location.ilike(pattern),
                    Project.sales.ilike(pattern),
                    Project.status.ilike(pattern),
                ))
            query = query.order_by(Project.created_at.desc())
            return query.count(), query.offset((page - 1) * page_size).limit(page_size).all()
        finally:
            session.close()
    
    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        session = get_session()
        try:
            return self._query(session).filter(Project.id == project_id).first()
        finally:
            session.close()
    
    def create_project(self, name: str, customer: str = None, project_code: str = None,
                      location: str = None, start_date: date = None, end_date: date = None,
                      sales: str = None, status: str = '待开始', remarks: str = None) -> Project:
        """创建项目；项目编号重复时直接报错"""
        session = get_session()
        try:
            name = require_text(name, "项目客户名称", PROJECT_FIELD_LIMITS["name"])
            project_code = optional_text(project_code, "订单编号", PROJECT_FIELD_LIMITS["project_code"]) or None
            customer = optional_text(customer, "兼容客户字段", PROJECT_FIELD_LIMITS["customer"])
            location = optional_text(location, "实施地点", PROJECT_FIELD_LIMITS["location"])
            sales = optional_text(sales, "销售", PROJECT_FIELD_LIMITS["sales"])
            remarks = optional_text(remarks, "项目备注", PROJECT_FIELD_LIMITS["remarks"])
            status = validate_choice(status, "项目状态", {"待开始", "实施中", "已完成", "已归档"})
            validate_date_range(start_date, end_date, "开始日期", "结束日期")

            if project_code:
                existing = session.query(Project).filter(Project.project_code == project_code).first()
                if existing:
                    raise ValueError("项目编号已存在，不能重复添加")

            project = Project(
                owner_id=owner_id_for(self.current_user),
                name=name,
                customer=customer,
                project_code=project_code,
                location=location,
                start_date=start_date,
                end_date=end_date,
                sales=sales,
                status=status,
                remarks=remarks
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_project(self, project_id: int, **kwargs) -> Optional[Project]:
        """更新项目"""
        session = get_session()
        try:
            project = self._query(session).filter(Project.id == project_id).first()
            if not project:
                return None

            start_date = kwargs.get("start_date", project.start_date)
            end_date = kwargs.get("end_date", project.end_date)
            validate_date_range(start_date, end_date, "开始日期", "结束日期")
            
            for key, value in kwargs.items():
                if hasattr(project, key):
                    if key == "name":
                        value = require_text(value, "项目客户名称", PROJECT_FIELD_LIMITS["name"])
                    elif key == "project_code":
                        value = optional_text(value, "订单编号", PROJECT_FIELD_LIMITS["project_code"]) or None
                        if value:
                            duplicate = (
                                session.query(Project)
                                .filter(Project.project_code == value, Project.id != project_id)
                                .first()
                            )
                            if duplicate:
                                raise ValueError("项目编号已存在，不能重复添加")
                    elif key == "customer":
                        value = optional_text(value, "客户名称", PROJECT_FIELD_LIMITS["customer"])
                    elif key == "location":
                        value = optional_text(value, "实施地点", PROJECT_FIELD_LIMITS["location"])
                    elif key == "sales":
                        value = optional_text(value, "销售", PROJECT_FIELD_LIMITS["sales"])
                    elif key == "remarks":
                        value = optional_text(value, "项目备注", PROJECT_FIELD_LIMITS["remarks"])
                    elif key == "status":
                        value = validate_choice(value, "项目状态", {"待开始", "实施中", "已完成", "已归档"})
                    setattr(project, key, value)
            
            session.commit()
            session.refresh(project)
            return project
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_project(self, project_id: int) -> bool:
        """删除项目"""
        session = get_session()
        try:
            project = self._query(session).filter(Project.id == project_id).first()
            if not project:
                return False
            
            # 删除项目只清理机器；其他业务资料保留，解除项目关联。
            session.query(Machine).filter(Machine.project_id == project_id).delete(
                synchronize_session=False
            )
            session.query(DailyReport).filter(DailyReport.project_id == project_id).update(
                {DailyReport.project_id: None}, synchronize_session=False
            )
            session.query(Expense).filter(Expense.project_id == project_id).update(
                {Expense.project_id: None}, synchronize_session=False
            )
            session.query(ImportFile).filter(ImportFile.project_id == project_id).update(
                {ImportFile.project_id: None}, synchronize_session=False
            )
            session.query(ImportRow).filter(ImportRow.project_id == project_id).update(
                {ImportRow.project_id: None}, synchronize_session=False
            )
            session.delete(project)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_all_projects(self) -> int:
        session = get_session()
        try:
            count = session.query(Project).count()
            session.query(Machine).delete(synchronize_session=False)
            session.query(DailyReport).update(
                {DailyReport.project_id: None}, synchronize_session=False
            )
            session.query(Expense).update(
                {Expense.project_id: None}, synchronize_session=False
            )
            session.query(ImportFile).update(
                {ImportFile.project_id: None}, synchronize_session=False
            )
            session.query(ImportRow).update(
                {ImportRow.project_id: None}, synchronize_session=False
            )
            session.query(Project).delete(synchronize_session=False)
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_project_stats(self) -> dict:
        """获取项目统计"""
        session = get_session()
        try:
            total, ongoing, completed = self._query(session).with_entities(
                func.count(Project.id),
                func.sum(case((Project.status == "实施中", 1), else_=0)),
                func.sum(case((Project.status == "已完成", 1), else_=0)),
            ).one()
            return {
                'total': int(total or 0),
                'ongoing': int(ongoing or 0),
                'completed': int(completed or 0),
            }
        finally:
            session.close()

    def get_completeness(self) -> dict:
        session = get_session()
        try:
            machine_counts = session.query(
                Machine.project_id.label("project_id"), func.count(Machine.id).label("count")
            ).group_by(Machine.project_id).subquery()
            report_counts = session.query(
                DailyReport.project_id.label("project_id"), func.count(DailyReport.id).label("count")
            ).group_by(DailyReport.project_id).subquery()
            expense_counts = session.query(
                Expense.project_id.label("project_id"), func.count(Expense.id).label("count")
            ).group_by(Expense.project_id).subquery()
            rows = session.query(
                Project.id, Project.name, Project.project_code, Project.customer,
                Project.location, Project.start_date, Project.sales, Project.status,
                func.coalesce(machine_counts.c.count, 0),
                func.coalesce(report_counts.c.count, 0),
                func.coalesce(expense_counts.c.count, 0),
            ).outerjoin(
                machine_counts, machine_counts.c.project_id == Project.id
            ).outerjoin(
                report_counts, report_counts.c.project_id == Project.id
            ).outerjoin(
                expense_counts, expense_counts.c.project_id == Project.id
            ).all()

            details = []
            for row in rows:
                checks = list(row[1:])
                score = round(sum(bool(value) for value in checks) * 100 / len(checks))
                missing = [label for label, value in zip(
                          ["项目客户名称", "订单编号", "客户", "地点", "开始日期", "销售", "状态", "机器", "SOP记录", "费用"], checks
                ) if not value]
                details.append({"id": row.id, "name": row.name, "score": score, "missing": missing})
            average = round(sum(item["score"] for item in details) / len(details)) if details else 0
            return {"average": average, "projects": details}
        finally:
            session.close()

    def get_dashboard_stats(self, owner_id=None) -> dict:
        """Return detached dashboard values using a fixed number of aggregate queries."""
        session = get_session()
        try:
            selected_owner_id = None
            if UserService.is_admin(self.current_user) and owner_id:
                selected_owner_id = int(owner_id)
            elif self.current_user and not UserService.is_admin(self.current_user):
                selected_owner_id = self.current_user.id

            project_scope = self._query(session)
            if selected_owner_id:
                project_scope = project_scope.filter(Project.owner_id == selected_owner_id)
            total, ongoing, completed = project_scope.with_entities(
                func.count(Project.id),
                func.sum(case((Project.status == "实施中", 1), else_=0)),
                func.sum(case((Project.status == "已完成", 1), else_=0)),
            ).one()
            total = int(total or 0)
            ongoing = int(ongoing or 0)
            completed = int(completed or 0)

            machine_scope = session.query(Machine).join(Project, Project.id == Machine.project_id)
            report_scope = session.query(DailyReport).join(Project, Project.id == DailyReport.project_id)
            import_scope = session.query(ImportFile).join(Project, Project.id == ImportFile.project_id)
            expense_scope = session.query(Expense).join(Project, Project.id == Expense.project_id)
            if selected_owner_id:
                machine_scope = machine_scope.filter(Project.owner_id == selected_owner_id)
                report_scope = report_scope.filter(Project.owner_id == selected_owner_id)
                import_scope = import_scope.filter(Project.owner_id == selected_owner_id)
                expense_scope = expense_scope.filter(Project.owner_id == selected_owner_id)
            machine_count = machine_scope.count()
            report_count = report_scope.count()
            import_count = import_scope.count()
            expense_breakdowns = [ExpenseService.amount_breakdown(row) for row in expense_scope.all()]
            actual_cost_total = sum(item["actual_cost"] for item in expense_breakdowns)
            assessment_total = sum(item["assessment_fee"] for item in expense_breakdowns)

            machine_counts = machine_scope.with_entities(
                Machine.project_id.label("project_id"), func.count(Machine.id).label("count")
            ).group_by(Machine.project_id).subquery()
            report_counts = report_scope.with_entities(
                DailyReport.project_id.label("project_id"), func.count(DailyReport.id).label("count")
            ).group_by(DailyReport.project_id).subquery()
            expense_counts = expense_scope.with_entities(
                Expense.project_id.label("project_id"), func.count(Expense.id).label("count")
            ).group_by(Expense.project_id).subquery()
            present_score = (
                case((func.nullif(Project.name, "").isnot(None), 1), else_=0)
                + case((func.nullif(Project.project_code, "").isnot(None), 1), else_=0)
                + case((func.nullif(Project.customer, "").isnot(None), 1), else_=0)
                + case((func.nullif(Project.location, "").isnot(None), 1), else_=0)
                + case((Project.start_date.isnot(None), 1), else_=0)
                + case((func.nullif(Project.sales, "").isnot(None), 1), else_=0)
                + case((func.nullif(Project.status, "").isnot(None), 1), else_=0)
                + case((func.coalesce(machine_counts.c.count, 0) > 0, 1), else_=0)
                + case((func.coalesce(report_counts.c.count, 0) > 0, 1), else_=0)
                + case((func.coalesce(expense_counts.c.count, 0) > 0, 1), else_=0)
            )
            completeness_score = present_score * 10
            completeness_avg, incomplete_count = project_scope.with_entities(
                func.coalesce(func.round(func.avg(completeness_score)), 0),
                func.sum(case((completeness_score < 100, 1), else_=0)),
            ).outerjoin(
                machine_counts, machine_counts.c.project_id == Project.id
            ).outerjoin(
                report_counts, report_counts.c.project_id == Project.id
            ).outerjoin(
                expense_counts, expense_counts.c.project_id == Project.id
            ).one()

            recent_machine_count = session.query(func.count(Machine.id)).filter(
                Machine.project_id == Project.id
            ).correlate(Project).scalar_subquery()
            recent_rows = self._query(session).with_entities(
                Project.name, Project.customer, recent_machine_count.label("machine_count"),
                Project.created_at, Project.status,
            ).order_by(Project.created_at.desc()).limit(5).all()

            recent_machines = session.query(
                Machine.ip, Machine.hostname, Machine.os, Machine.gpu, Machine.project_id
            ).join(Project, Project.id == Machine.project_id)
            if selected_owner_id:
                recent_machines = recent_machines.filter(Project.owner_id == selected_owner_id)
            recent_machines = recent_machines.order_by(Machine.created_at.desc()).limit(5).all()
            trend_start = date.today() - timedelta(days=6)
            daily_trend = []
            for offset in range(7):
                day = trend_start + timedelta(days=offset)
                day_end = day + timedelta(days=1)
                project_query = self._query(session).filter(Project.created_at >= day, Project.created_at < day_end)
                machine_query = session.query(Machine).join(Project, Project.id == Machine.project_id)
                import_query = session.query(ImportFile).join(Project, Project.id == ImportFile.project_id)
                if selected_owner_id:
                    project_query = project_query.filter(Project.owner_id == selected_owner_id)
                    machine_query = machine_query.filter(Project.owner_id == selected_owner_id)
                    import_query = import_query.filter(Project.owner_id == selected_owner_id)
                daily_trend.append({
                    "日期": day.strftime("%m-%d"),
                    "项目数": project_query.count(),
                    "机器数": machine_query.filter(Machine.created_at >= day, Machine.created_at < day_end).count(),
                    "导入文件数": import_query.filter(ImportFile.imported_at >= day, ImportFile.imported_at < day_end).count(),
                })
            activity_rows = []
            for row in import_scope.order_by(ImportFile.imported_at.desc()).limit(3).all():
                activity_rows.append([
                    "导入文件",
                    f"{row.file_name}",
                    row.imported_at.strftime("%Y-%m-%d %H:%M") if row.imported_at else "-",
                ])
            for row in project_scope.order_by(Project.created_at.desc()).limit(2).all():
                activity_rows.append([
                    "新增项目",
                    row.name,
                    row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "-",
                ])
            activity_rows = activity_rows[:5]

            status_distribution = [
                [label or "未填写", int(count or 0)]
                for label, count in project_scope.with_entities(Project.status, func.count(Project.id))
                .group_by(Project.status).order_by(func.count(Project.id).desc()).all()
            ]
            expense_distribution = [
                [label or "未分类", float(total or 0)]
                for label, total in expense_scope.with_entities(
                    Expense.expense_category, func.coalesce(func.sum(Expense.amount), 0)
                ).group_by(Expense.expense_category).order_by(func.sum(Expense.amount).desc()).all()
            ]
            report_distribution = [
                [label or "未填写", int(count or 0)]
                for label, count in report_scope.with_entities(DailyReport.status, func.count(DailyReport.id))
                .group_by(DailyReport.status).order_by(func.count(DailyReport.id).desc()).all()
            ]
            current_year = datetime.now().year
            expense_by_month_query = {
                int(month): float(total or 0)
                for month, total in expense_scope.with_entities(
                    func.strftime("%m", Expense.expense_date),
                    func.coalesce(func.sum(Expense.amount), 0),
                ).filter(Expense.expense_date >= date(current_year, 1, 1)).filter(
                    Expense.expense_date < date(current_year + 1, 1, 1)
                ).group_by(
                    func.strftime("%m", Expense.expense_date)
                ).all()
            }
            expense_by_month = [[f"{month:02d}月", expense_by_month_query.get(month, 0.0)] for month in range(1, 13)]
            bucket_expr = case(
                (completeness_score >= 100, "100%"),
                (completeness_score >= 80, "80-99%"),
                (completeness_score >= 60, "60-79%"),
                else_="0-59%",
            )
            bucket_counts = dict(project_scope.with_entities(
                bucket_expr, func.count(Project.id)
            ).outerjoin(
                machine_counts, machine_counts.c.project_id == Project.id
            ).outerjoin(
                report_counts, report_counts.c.project_id == Project.id
            ).outerjoin(
                expense_counts, expense_counts.c.project_id == Project.id
            ).group_by(bucket_expr).all())
            completeness_distribution = [
                [label, int(bucket_counts.get(label, 0))]
                for label in ("100%", "80-99%", "60-79%", "0-59%")
            ]
            user_summaries = []
            if UserService.is_admin(self.current_user):
                users_query = session.query(User)
                if selected_owner_id:
                    users_query = users_query.filter(User.id == selected_owner_id)
                users = users_query.order_by(User.created_at, User.id).all()
                for user in users:
                    user_projects = session.query(Project).filter(Project.owner_id == user.id)
                    user_project_ids = [
                        project_id for (project_id,) in user_projects.with_entities(Project.id).all()
                    ]
                    user_machine_count = (
                        session.query(func.count(Machine.id))
                        .filter(Machine.project_id.in_(user_project_ids))
                        .scalar()
                        if user_project_ids else 0
                    )
                    user_import_count = (
                        session.query(func.count(ImportFile.id))
                        .filter(ImportFile.project_id.in_(user_project_ids))
                        .scalar()
                        if user_project_ids else 0
                    )
                    user_expenses = session.query(Expense).filter(Expense.owner_id == user.id).all()
                    user_breakdowns = [ExpenseService.amount_breakdown(row) for row in user_expenses]
                    user_assessment = sum(item["assessment_fee"] for item in user_breakdowns)
                    user_actual_cost = sum(item["actual_cost"] for item in user_breakdowns)
                    user_summaries.append([
                        f"{user.display_name}（{user.username}）",
                        "系统管理员" if user.role == "admin" else "普通用户",
                        "启用" if user.is_active else "停用",
                        user_projects.count(),
                        int(user_machine_count or 0),
                        int(user_import_count or 0),
                        f"{user_assessment:.2f}",
                        f"{user_actual_cost:.2f}",
                        f"{user_assessment - user_actual_cost:.2f}",
                    ])

            return {
                "total_projects": total,
                "ongoing": ongoing,
                "completed": completed,
                "total_machines": int(machine_count or 0),
                "total_reports": int(report_count or 0),
                "expense_total": actual_cost_total,
                "assessment_fee_total": assessment_total,
                "actual_cost_total": actual_cost_total,
                "profit_total": assessment_total - actual_cost_total,
                "import_count": int(import_count or 0),
                "completeness": int(completeness_avg or 0),
                "incomplete_count": int(incomplete_count or 0),
                "recent_projects": [
                    [
                        row.name,
                        row.customer or "-",
                        row.machine_count,
                        row.created_at.strftime("%Y-%m-%d") if row.created_at else "-",
                        row.status,
                    ]
                    for row in recent_rows
                ],
                "recent_machines": [
                    [
                        row.ip or "-",
                        row.hostname or "-",
                        row.os or "-",
                        row.gpu or "-",
                        "在线",
                    ]
                    for row in recent_machines
                ],
                "recent_activities": activity_rows,
                "daily_trend": daily_trend,
                "status_distribution": status_distribution,
                "expense_distribution": expense_distribution,
                "report_distribution": report_distribution,
                "expense_by_month": expense_by_month,
                "completeness_distribution": completeness_distribution,
                "user_summaries": user_summaries,
                "dashboard_year": current_year,
            }
        finally:
            session.close()
