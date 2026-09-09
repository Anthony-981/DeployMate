from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Machine(Base):
    __tablename__ = 'machines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'))
    ip = Column(String(50), nullable=False, index=True)
    role = Column(String(100))
    business_ip = Column(String(50))
    cluster_ip = Column(String(50))
    compute_ip = Column(String(50))
    storage_ip = Column(String(50))
    hostname = Column(String(200))
    os = Column(String(200))
    cpu = Column(String(200))
    memory = Column(String(100))
    gpu_count = Column(String(50))
    gpu_model = Column(String(200))
    gpu_interconnect = Column(String(50))
    gpu = Column(String(200))
    cuda = Column(String(100))
    docker = Column(String(100))
    username = Column(String(100))
    account = Column(String(100))
    password = Column(String(200))
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    project = relationship("Project", back_populates="machines")
    
    # 同一项目内 IP 唯一
    __table_args__ = (
        UniqueConstraint('project_id', 'ip', name='uq_project_ip'),
    )
    
    def __repr__(self):
        return f"<Machine(id={self.id}, ip='{self.ip}', hostname='{self.hostname}')>"
