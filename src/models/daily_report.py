from sqlalchemy import Column, Integer, String, Date, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class DailyReport(Base):
    __tablename__ = 'daily_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    report_date = Column(Date, nullable=False, index=True)
    work_content = Column(Text)
    problems = Column(Text)
    solutions = Column(Text)
    next_plan = Column(Text)
    remarks = Column(Text)
    status = Column(String(50), default='草稿')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    project = relationship("Project", back_populates="daily_reports")
    owner = relationship("User", foreign_keys=[owner_id])
    
    # 一个项目一天一条 SOP 问题记录
    __table_args__ = (
        UniqueConstraint('project_id', 'report_date', name='uq_project_date'),
    )

    # Keep the existing SQLite columns for backward compatibility while exposing
    # the new SOP terminology to future callers.
    @property
    def sop_topic(self):
        return self.work_content

    @sop_topic.setter
    def sop_topic(self, value):
        self.work_content = value

    @property
    def sop_problem(self):
        return self.problems

    @sop_problem.setter
    def sop_problem(self, value):
        self.problems = value

    @property
    def solution_method(self):
        return self.solutions

    @solution_method.setter
    def solution_method(self, value):
        self.solutions = value
    
    def __repr__(self):
        return f"<DailyReport(id={self.id}, date='{self.report_date}', status='{self.status}')>"
