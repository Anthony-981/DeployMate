from sqlalchemy import Column, Integer, String, Date, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    expense_date = Column(Date, nullable=False, index=True)
    travel_person = Column(String(100))
    travel_start_date = Column(Date)
    travel_end_date = Column(Date)
    expense_category = Column(String(30), nullable=True, index=True)
    expense_type = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    assessment_fee = Column(Numeric(10, 2), nullable=True)
    actual_cost = Column(Numeric(10, 2), nullable=True)
    remarks = Column(Text)
    is_reimbursed = Column(String(50), default='未提交')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    project = relationship("Project", back_populates="expenses")
    owner = relationship("User", foreign_keys=[owner_id])
    
    def __repr__(self):
        return f"<Expense(id={self.id}, type='{self.expense_type}', amount={self.amount})>"
