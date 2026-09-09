from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    expense_date = Column(Date, nullable=False, index=True)
    expense_type = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    remarks = Column(Text)
    is_reimbursed = Column(String(50), default='未提交')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    project = relationship("Project", back_populates="expenses")
    
    def __repr__(self):
        return f"<Expense(id={self.id}, type='{self.expense_type}', amount={self.amount})>"
