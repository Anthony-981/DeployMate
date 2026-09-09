from sqlalchemy import create_engine
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
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

def get_session():
    """获取数据库会话"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return SessionLocal()
