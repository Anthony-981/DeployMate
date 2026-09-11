from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class ImportRow(Base):
    __tablename__ = "import_rows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    project_id = Column(Integer, nullable=True)
    file_name = Column(String(260), nullable=False)
    sheet_name = Column(String(200), nullable=False)
    row_number = Column(Integer, nullable=False)
    row_json = Column(Text, nullable=False)
    import_status = Column(String(50), nullable=False, default="原始数据已保存")
    created_at = Column(DateTime, default=datetime.now)
    owner = relationship("User", foreign_keys=[owner_id])
