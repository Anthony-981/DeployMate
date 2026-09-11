from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime

class Base(DeclarativeBase):
    pass

# 数据库引擎和会话（将在 db_service 中初始化）
engine = None
SessionLocal = None

def init_db(db_path: str):
    """初始化数据库"""
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    engine = create_engine(f'sqlite:///{db_path}', echo=False)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

def get_session():
    """获取数据库会话"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()
