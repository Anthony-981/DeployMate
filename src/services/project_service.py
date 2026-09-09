from typing import List, Optional
from datetime import date
from src.models import Project, Machine, DailyReport, Expense, ImportFile, ImportRow, get_session
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
    def __init__(self):
        pass
    
    def get_all_projects(self) -> List[Project]:
        """获取所有项目"""
        session = get_session()
        try:
            return session.query(Project).order_by(Project.created_at.desc()).all()
        finally:
            session.close()

    def get_projects_page(self, page=1, page_size=20):
        session = get_session()
        try:
            query = session.query(Project).order_by(Project.created_at.desc())
            return query.count(), query.offset((page - 1) * page_size).limit(page_size).all()
        finally:
            session.close()
    
    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """根据ID获取项目"""
        session = get_session()
        try:
            return session.query(Project).filter(Project.id == project_id).first()
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
            project = session.query(Project).filter(Project.id == project_id).first()
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
            project = session.query(Project).filter(Project.id == project_id).first()
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
            total = session.query(Project).count()
            ongoing = session.query(Project).filter(Project.status == '实施中').count()
            completed = session.query(Project).filter(Project.status == '已完成').count()
            
            return {
                'total': total,
                'ongoing': ongoing,
                'completed': completed
            }
        finally:
            session.close()

    def get_completeness(self) -> dict:
        session = get_session()
        projects = session.query(Project).all()
        details = []
        try:
            for project in projects:
                checks = [project.name, project.project_code, project.customer, project.location,
                          project.start_date, project.sales, project.status,
                          session.query(Machine).filter(Machine.project_id == project.id).count(),
                          session.query(DailyReport).filter(DailyReport.project_id == project.id).count(),
                          session.query(Expense).filter(Expense.project_id == project.id).count()]
                score = round(sum(bool(value) for value in checks) * 100 / len(checks))
                missing = [label for label, value in zip(
                          ["项目客户名称", "订单编号", "客户", "地点", "开始日期", "销售", "状态", "机器", "SOP记录", "费用"], checks
                ) if not value]
                details.append({"id": project.id, "name": project.name, "score": score, "missing": missing})
            average = round(sum(item["score"] for item in details) / len(details)) if details else 0
            return {"average": average, "projects": details}
        finally:
            session.close()
