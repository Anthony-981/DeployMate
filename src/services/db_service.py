import os
from pathlib import Path
from sqlalchemy import text, inspect
from src.config import resolve_db_path, get_db_mode
from src.models import init_db, get_session, Project, Machine, DailyReport, Expense, ImportFile, ImportRow

class DatabaseService:
    def __init__(self, db_path: str = None, db_mode: str = None):
        self.db_mode = (db_mode or get_db_mode()).strip().lower()
        self.db_path = resolve_db_path(db_path, self.db_mode)
        init_db(self.db_path)
        self.migrate_project_columns()
        self.migrate_machine_columns()
        self.migrate_expense_columns()
        self.migrate_user_columns()
        self.migrate_owner_columns()
        self.migrate_detachable_project_columns()
        self.ensure_performance_indexes()
    
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
                'extra_info': 'TEXT',
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    session.execute(text(f'ALTER TABLE machines ADD COLUMN {column_name} {column_type}'))
            session.commit()
        finally:
            session.close()

    def migrate_expense_columns(self):
        """Add expense metadata used for assessment and profit reporting."""
        session = self.get_session()
        try:
            inspector = inspect(session.get_bind())
            if "expenses" not in inspector.get_table_names():
                return
            existing = {col["name"] for col in inspector.get_columns("expenses")}
            if "expense_type" not in existing:
                session.execute(text("ALTER TABLE expenses ADD COLUMN expense_type VARCHAR(50)"))
            columns = {
                "travel_person": "VARCHAR(100)",
                "travel_start_date": "DATE",
                "travel_end_date": "DATE",
                "expense_category": "VARCHAR(30)",
                "assessment_fee": "NUMERIC(10, 2)",
                "actual_cost": "NUMERIC(10, 2)",
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    session.execute(text(
                        f"ALTER TABLE expenses ADD COLUMN {column_name} {column_type}"
                    ))
            session.execute(text("""
                UPDATE expenses
                SET expense_category = CASE
                    WHEN expense_type = '出差考核费用' THEN '考核费用'
                    ELSE '出差费用'
                END
                WHERE (expense_category IS NULL OR expense_category = '')
                  AND assessment_fee IS NULL
                  AND actual_cost IS NULL
            """))
            session.commit()
        finally:
            session.close()

    def migrate_user_columns(self):
        """Add roles to user tables created before role-based access."""
        session = self.get_session()
        try:
            inspector = inspect(session.get_bind())
            if "users" not in inspector.get_table_names():
                return
            existing = {col["name"] for col in inspector.get_columns("users")}
            if "role" not in existing:
                session.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
                first_user = session.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).first()
                if first_user:
                    session.execute(
                        text("UPDATE users SET role = 'admin' WHERE id = :user_id"),
                        {"user_id": first_user[0]},
                    )
            session.commit()
        finally:
            session.close()

    def migrate_owner_columns(self):
        """Add user ownership and assign legacy rows to the first administrator."""
        session = self.get_session()
        try:
            inspector = inspect(session.get_bind())
            tables = ("projects", "machines", "daily_reports", "expenses", "import_files", "import_rows")
            for table_name in tables:
                if table_name not in inspector.get_table_names():
                    continue
                columns = {column["name"] for column in inspector.get_columns(table_name)}
                if "owner_id" not in columns:
                    session.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN owner_id INTEGER"
                    ))

            admin = session.execute(
                text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
            ).first()
            if not admin:
                admin = session.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).first()
            if admin:
                owner_id = admin[0]
                session.execute(text(
                    "UPDATE projects SET owner_id = :owner_id WHERE owner_id IS NULL"
                ), {"owner_id": owner_id})
                for table_name in ("machines", "daily_reports", "expenses", "import_files", "import_rows"):
                    if table_name in inspector.get_table_names():
                        session.execute(text(
                            f"""UPDATE {table_name}
                                SET owner_id = (
                                    SELECT owner_id FROM projects
                                    WHERE projects.id = {table_name}.project_id
                                )
                                WHERE owner_id IS NULL AND project_id IS NOT NULL"""
                        ))
                        session.execute(text(
                            f"UPDATE {table_name} SET owner_id = :owner_id WHERE owner_id IS NULL"
                        ), {"owner_id": owner_id})
            session.commit()
        finally:
            session.close()

    def migrate_detachable_project_columns(self):
        """Allow retained history to outlive its deleted project in old SQLite files."""
        session = self.get_session()
        try:
            bind = session.get_bind()
            inspector = inspect(bind)
            for table_name, create_sql, columns in (
                ("daily_reports", """
                    CREATE TABLE daily_reports (
                        id INTEGER NOT NULL,
                        owner_id INTEGER,
                        project_id INTEGER,
                        report_date DATE NOT NULL,
                        work_content TEXT,
                        problems TEXT,
                        solutions TEXT,
                        next_plan TEXT,
                        remarks TEXT,
                        status VARCHAR(50),
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_project_date UNIQUE (project_id, report_date),
                        FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
                        FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT
                    )
                """, (
                    "id", "owner_id", "project_id", "report_date", "work_content", "problems",
                    "solutions", "next_plan", "remarks", "status", "created_at", "updated_at",
                )),
                ("expenses", """
                    CREATE TABLE expenses (
                        id INTEGER NOT NULL,
                        owner_id INTEGER,
                        project_id INTEGER,
                        expense_date DATE NOT NULL,
                        travel_person VARCHAR(100),
                        travel_start_date DATE,
                        travel_end_date DATE,
                        expense_category VARCHAR(30),
                        expense_type VARCHAR(50) NOT NULL,
                        amount NUMERIC(10, 2) NOT NULL,
                        assessment_fee NUMERIC(10, 2),
                        actual_cost NUMERIC(10, 2),
                        remarks TEXT,
                        is_reimbursed VARCHAR(50),
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL,
                        FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT
                    )
                """, (
                    "id", "owner_id", "project_id", "expense_date", "travel_person",
                    "travel_start_date", "travel_end_date", "expense_category", "expense_type", "amount",
                    "assessment_fee", "actual_cost", "remarks", "is_reimbursed", "created_at", "updated_at",
                )),
            ):
                if table_name not in inspector.get_table_names():
                    continue
                project_column = next(
                    column for column in inspector.get_columns(table_name)
                    if column["name"] == "project_id"
                )
                if project_column["nullable"]:
                    continue

                temporary_name = f"{table_name}__nullable_project"
                session.execute(text(f"DROP TABLE IF EXISTS {temporary_name}"))
                for index in inspector.get_indexes(table_name):
                    session.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))
                session.execute(text(f"ALTER TABLE {table_name} RENAME TO {temporary_name}"))
                session.execute(text(create_sql))
                quoted_columns = ", ".join(columns)
                session.execute(text(
                    f"INSERT INTO {table_name} ({quoted_columns}) "
                    f"SELECT {quoted_columns} FROM {temporary_name}"
                ))
                session.execute(text(f"DROP TABLE {temporary_name}"))
            session.commit()
        finally:
            session.close()

    def ensure_performance_indexes(self):
        """Create indexes used by dashboard aggregates and paged project views."""
        statements = (
            "CREATE INDEX IF NOT EXISTS ix_projects_status ON projects(status)",
            "CREATE INDEX IF NOT EXISTS ix_projects_created_at ON projects(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_machines_project_id ON machines(project_id)",
            "CREATE INDEX IF NOT EXISTS ix_daily_reports_project_id ON daily_reports(project_id)",
            "CREATE INDEX IF NOT EXISTS ix_expenses_project_id ON expenses(project_id)",
            "CREATE INDEX IF NOT EXISTS ix_expenses_project_date ON expenses(project_id, expense_date)",
            "CREATE INDEX IF NOT EXISTS ix_import_files_project_id ON import_files(project_id)",
            "CREATE INDEX IF NOT EXISTS ix_import_files_imported_at ON import_files(imported_at)",
            "CREATE INDEX IF NOT EXISTS ix_import_rows_project_id ON import_rows(project_id)",
            "CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_machines_owner_id ON machines(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_daily_reports_owner_id ON daily_reports(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_expenses_owner_id ON expenses(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_import_files_owner_id ON import_files(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_import_rows_owner_id ON import_rows(owner_id)",
        )
        session = self.get_session()
        try:
            for statement in statements:
                session.execute(text(statement))
            session.commit()
        finally:
            session.close()
    
