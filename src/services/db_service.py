import os
from pathlib import Path
from sqlalchemy import text, inspect
from src.config import resolve_db_path, get_db_mode
from src.models import init_db, get_session, Project, Machine, DailyReport, Expense, ImportFile

class DatabaseService:
    def __init__(self, db_path: str = None, db_mode: str = None):
        self.db_mode = (db_mode or get_db_mode()).strip().lower()
        self.db_path = resolve_db_path(db_path, self.db_mode)
        init_db(self.db_path)
        self.migrate_project_columns()
        self.migrate_machine_columns()
    
    def get_session(self):
        """获取数据库会话"""
        return get_session()

    def migrate_project_columns(self):
        """Add project fields introduced after the initial database release."""
        session = self.get_session()
        try:
            inspector = inspect(session.get_bind())
            if 'projects' not in inspector.get_table_names():
                return
            existing = {col['name'] for col in inspector.get_columns('projects')}
            if 'sales' not in existing:
                session.execute(text('ALTER TABLE projects ADD COLUMN sales VARCHAR(100)'))
            session.commit()
        finally:
            session.close()

    def migrate_machine_columns(self):
        """给旧版 machines 表补充新字段"""
        session = self.get_session()
        try:
            inspector = inspect(session.get_bind())
            if 'machines' not in inspector.get_table_names():
                return

            existing = {col['name'] for col in inspector.get_columns('machines')}
            columns = {
                'role': 'VARCHAR(100)',
                'business_ip': 'VARCHAR(50)',
                'cluster_ip': 'VARCHAR(50)',
                'compute_ip': 'VARCHAR(50)',
                'storage_ip': 'VARCHAR(50)',
                'gpu_count': 'VARCHAR(50)',
                'gpu_model': 'VARCHAR(200)',
                'gpu_interconnect': 'VARCHAR(50)',
                'username': 'VARCHAR(100)',
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    session.execute(text(f'ALTER TABLE machines ADD COLUMN {column_name} {column_type}'))
            session.commit()
        finally:
            session.close()
    
    def create_sample_data(self):
        """创建示例数据（用于测试）"""
        session = self.get_session()
        try:
            # 检查是否已有数据
            if session.query(Project).count() > 0:
                return
            
            # 创建示例项目
            from datetime import date
            project = Project(
                name='XX AI智慧平台',
                customer='XX科技有限公司',
                project_code='XM-2026-0901',
                location='上海',
                start_date=date(2026, 9, 1),
                sales='徐明生',
                status='实施中'
            )
            session.add(project)
            session.commit()
            
            # 创建示例机器
            machines = [
                Machine(
                    project_id=project.id,
                    ip='10.10.10.20',
                    role='GPU计算节点',
                    business_ip='172.16.10.20',
                    cluster_ip='10.20.0.20',
                    compute_ip='10.30.0.20',
                    storage_ip='10.40.0.20',
                    hostname='gpu-server01',
                    os='Ubuntu 22.04',
                    cpu='64C',
                    memory='256G',
                    gpu_count='2',
                    gpu_model='A800 80G',
                    gpu='A800 80G x 2',
                    cuda='12.4',
                    docker='27.3',
                    username='root',
                    account='root'
                ),
                Machine(
                    project_id=project.id,
                    ip='10.10.10.21',
                    role='应用节点',
                    business_ip='172.16.10.21',
                    cluster_ip='10.20.0.21',
                    compute_ip='10.30.0.21',
                    storage_ip='10.40.0.21',
                    hostname='app-server01',
                    os='CentOS 7.9',
                    cpu='32C',
                    memory='128G',
                    gpu_count='0',
                    gpu_model='',
                    docker='24.0',
                    username='deploy',
                    account='deploy'
                ),
            ]
            session.add_all(machines)
            
            # 创建示例费用
            expenses = [
                Expense(
                    project_id=project.id,
                    expense_date=date(2026, 9, 7),
                    expense_type='交通',
                    amount=173,
                    remarks='高铁'
                ),
                Expense(
                    project_id=project.id,
                    expense_date=date(2026, 9, 7),
                    expense_type='住宿',
                    amount=380,
                    remarks='客户现场附近酒店'
                ),
            ]
            session.add_all(expenses)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
