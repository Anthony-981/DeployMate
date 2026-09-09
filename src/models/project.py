from sqlalchemy import Column, Integer, String, Date, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Project(Base):
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    customer = Column(String(200))
    project_code = Column(String(100), unique=True)
    location = Column(String(200))
    start_date = Column(Date)
    end_date = Column(Date)
    sales = Column(String(100))
    status = Column(String(50), default='待开始')
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    machines = relationship("Machine", back_populates="project", cascade="all, delete-orphan")
    daily_reports = relationship("DailyReport", back_populates="project", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="project", cascade="all, delete-orphan")
    import_files = relationship("ImportFile", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"
