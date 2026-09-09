from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class ImportFile(Base):
    __tablename__ = 'import_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'))
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    records_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    merge_count = Column(Integer, default=0)
    conflict_count = Column(Integer, default=0)
    status = Column(String(50), default='待分析')
    imported_at = Column(DateTime, default=datetime.now)
    
    # 关系
    project = relationship("Project", back_populates="import_files")
    
    def __repr__(self):
        return f"<ImportFile(id={self.id}, name='{self.file_name}', status='{self.status}')>"
