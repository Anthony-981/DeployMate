from typing import List, Optional
from src.models import Machine, get_session
from src.models import Project
from sqlalchemy import or_, cast, String
from src.utils.validators import (
    MACHINE_FIELD_LIMITS,
    ValidationError,
    clean_text,
    optional_text,
    validate_ipv4,
    validate_positive_int_string,
    require_text,
)

class MachineService:
    def __init__(self):
        pass
    
    def get_machines_by_project(self, project_id: int) -> List[Machine]:
        """获取项目的所有机器"""
        session = get_session()
        try:
            return session.query(Machine).filter(Machine.project_id == project_id).all()
        finally:
            session.close()

    def get_all_machines(self) -> List[Machine]:
        session = get_session()
        try:
            return session.query(Machine).order_by(Machine.project_id, Machine.id).all()
        finally:
            session.close()

    def get_machines_page(self, page=1, page_size=20, project_id=None, search=""):
        session = get_session()
        try:
            query = session.query(Machine)
            if project_id:
                query = query.filter(Machine.project_id == project_id)
            keyword = (search or "").strip()
            if keyword:
                pattern = f"%{keyword}%"
                query = query.join(Project, Project.id == Machine.project_id).filter(or_(
                    Project.name.ilike(pattern), Project.project_code.ilike(pattern),
                    *[cast(getattr(Machine, field), String).ilike(pattern) for field in (
                        "role", "ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip",
                        "username", "account", "password", "gpu_count", "gpu_model",
                        "gpu_interconnect", "hostname", "os", "cpu", "memory", "gpu", "cuda", "docker",
                    )]
                ))
            query = query.order_by(Machine.project_id, Machine.id)
            return query.count(), query.offset((page - 1) * page_size).limit(page_size).all()
        finally:
            session.close()
    
    def get_machine_by_ip(self, project_id: int, ip: str) -> Optional[Machine]:
        """根据IP获取机器（用于合并判断）"""
        session = get_session()
        try:
            return session.query(Machine).filter(
                Machine.project_id == project_id,
                Machine.ip == ip
            ).first()
        finally:
            session.close()

    def get_machine_by_id(self, machine_id: int) -> Optional[Machine]:
        session = get_session()
        try:
            return session.query(Machine).filter(Machine.id == machine_id).first()
        finally:
            session.close()
    
    def create_machine(
        self,
        project_id: int,
        ip: str,
        role: str = None,
        business_ip: str = None,
        cluster_ip: str = None,
        compute_ip: str = None,
        storage_ip: str = None,
        hostname: str = None,
        os: str = None,
        cpu: str = None,
        memory: str = None,
        gpu_count: str = None,
        gpu_model: str = None,
        gpu_interconnect: str = None,
        gpu: str = None,
        cuda: str = None,
        docker: str = None,
        username: str = None,
        account: str = None,
        password: str = None,
        remarks: str = None
    ) -> Machine:
        """创建机器"""
        session = get_session()
        try:
            if not project_id or int(project_id) <= 0:
                raise ValidationError("项目不能为空")
            ip = validate_ipv4(ip, "IP", required=True)
            role = optional_text(role, "角色", MACHINE_FIELD_LIMITS["role"])
            business_ip = validate_ipv4(business_ip, "业务网IP")
            cluster_ip = validate_ipv4(cluster_ip, "集群网IP")
            self._validate_required_network(business_ip, cluster_ip)
            compute_ip = validate_ipv4(compute_ip, "计算网IP")
            storage_ip = validate_ipv4(storage_ip, "存储网IP")
            hostname = optional_text(hostname, "主机名", MACHINE_FIELD_LIMITS["hostname"])
            os = optional_text(os, "OS", MACHINE_FIELD_LIMITS["os"])
            cpu = optional_text(cpu, "CPU", MACHINE_FIELD_LIMITS["cpu"])
            memory = optional_text(memory, "内存", MACHINE_FIELD_LIMITS["memory"])
            gpu_count = validate_positive_int_string(gpu_count, "GPU数量", max_len=MACHINE_FIELD_LIMITS["gpu_count"])
            gpu_model = optional_text(gpu_model, "GPU型号", MACHINE_FIELD_LIMITS["gpu_model"])
            gpu_interconnect = optional_text(gpu_interconnect, "GPU互联方式", MACHINE_FIELD_LIMITS["gpu_interconnect"])
            gpu = optional_text(gpu, "GPU", MACHINE_FIELD_LIMITS["gpu"])
            cuda = optional_text(cuda, "CUDA", MACHINE_FIELD_LIMITS["cuda"])
            docker = optional_text(docker, "Docker", MACHINE_FIELD_LIMITS["docker"])
            username = optional_text(username, "用户名", MACHINE_FIELD_LIMITS["username"])
            account = optional_text(account, "账号", MACHINE_FIELD_LIMITS["username"])
            password = optional_text(password, "密码", MACHINE_FIELD_LIMITS["password"])
            remarks = optional_text(remarks, "备注", MACHINE_FIELD_LIMITS["remarks"])

            duplicate = session.query(Machine).filter(
                Machine.project_id == project_id,
                Machine.ip == ip,
            ).first()
            if duplicate:
                raise ValidationError("该项目中已存在相同管理网IP的机器")

            machine = Machine(
                project_id=project_id,
                ip=ip,
                role=role,
                business_ip=business_ip,
                cluster_ip=cluster_ip,
                compute_ip=compute_ip,
                storage_ip=storage_ip,
                hostname=hostname,
                os=os,
                cpu=cpu,
                memory=memory,
                gpu_count=gpu_count,
                gpu_model=gpu_model,
                gpu_interconnect=gpu_interconnect,
                gpu=gpu,
                cuda=cuda,
                docker=docker,
                username=username,
                account=account,
                password=password,
                remarks=remarks
            )
            session.add(machine)
            session.commit()
            session.refresh(machine)
            return machine
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_machine(self, machine_id: int, **kwargs) -> Optional[Machine]:
        """更新机器"""
        session = get_session()
        try:
            machine = session.query(Machine).filter(Machine.id == machine_id).first()
            if not machine:
                return None

            target_project_id = int(kwargs.get("project_id", machine.project_id))
            target_ip = validate_ipv4(kwargs.get("ip", machine.ip), "IP", required=True)
            duplicate = session.query(Machine).filter(
                Machine.project_id == target_project_id,
                Machine.ip == target_ip,
                Machine.id != machine_id,
            ).first()
            if duplicate:
                raise ValidationError("该项目中已存在相同管理网IP的机器")
            
            for key, value in kwargs.items():
                if hasattr(machine, key):
                    if key in ["ip", "business_ip", "cluster_ip", "compute_ip", "storage_ip"]:
                        value = validate_ipv4(value, key.replace("_", "").upper() if key != "ip" else "IP", required=(key == "ip"))
                    elif key in ["role", "hostname", "os", "cpu", "memory", "gpu_model", "gpu_interconnect", "gpu", "cuda", "docker", "username", "account", "password", "remarks"]:
                        value = optional_text(value, key, MACHINE_FIELD_LIMITS.get(key, 100))
                    elif key == "gpu_count":
                        value = validate_positive_int_string(value, "GPU数量", max_len=MACHINE_FIELD_LIMITS["gpu_count"])
                    setattr(machine, key, value)
            self._validate_required_network(machine.business_ip, machine.cluster_ip)
            
            session.commit()
            session.refresh(machine)
            return machine
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def merge_machine_data(self, project_id: int, ip: str, new_data: dict) -> tuple[Machine, bool, dict]:
        """
        合并机器数据
        返回: (机器对象, 是否新增, 冲突字段字典)
        """
        session = get_session()
        try:
            project_id = int(project_id)
            ip = validate_ipv4(ip, "IP", required=True)
            cleaned_data = self._clean_machine_payload(new_data)
            existing = session.query(Machine).filter(
                Machine.project_id == project_id,
                Machine.ip == ip
            ).first()
            
            conflicts = {}
            
            if existing:
                # 已存在，检查冲突
                for key, new_value in cleaned_data.items():
                    if key in ['ip', 'project_id']:
                        continue
                    
                    old_value = getattr(existing, key, None)
                    if old_value and new_value and old_value != new_value:
                        conflicts[key] = {'old': old_value, 'new': new_value}
                    elif not old_value and new_value:
                        # 补充空字段
                        setattr(existing, key, new_value)
                self._validate_required_network(existing.business_ip, existing.cluster_ip)
                
                session.commit()
                session.refresh(existing)
                return existing, False, conflicts
            else:
                # 新增
                self._validate_required_network(cleaned_data.get("business_ip"), cleaned_data.get("cluster_ip"))
                machine = Machine(project_id=project_id, ip=ip, **cleaned_data)
                session.add(machine)
                session.commit()
                session.refresh(machine)
                return machine, True, {}
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def delete_machine(self, machine_id: int) -> bool:
        """删除机器"""
        session = get_session()
        try:
            machine = session.query(Machine).filter(Machine.id == machine_id).first()
            if not machine:
                return False
            
            session.delete(machine)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_machine_count(self) -> int:
        """获取机器总数"""
        session = get_session()
        try:
            return session.query(Machine).count()
        finally:
            session.close()

    def _clean_machine_payload(self, payload: dict) -> dict:
        cleaned = {}
        for key, value in payload.items():
            if key in ["ip", "project_id"]:
                continue
            if key in ["business_ip", "cluster_ip", "compute_ip", "storage_ip"]:
                cleaned[key] = validate_ipv4(value, key.replace("_", "").upper())
            elif key == "gpu_count":
                cleaned[key] = validate_positive_int_string(value, "GPU数量", max_len=MACHINE_FIELD_LIMITS["gpu_count"])
            elif key in MACHINE_FIELD_LIMITS:
                cleaned[key] = optional_text(value, key, MACHINE_FIELD_LIMITS[key])
            else:
                cleaned[key] = clean_text(value)
        return cleaned

    @staticmethod
    def _validate_required_network(business_ip: str, cluster_ip: str):
        if not business_ip and not cluster_ip:
            raise ValidationError("业务网IP或集群网IP至少填写一个")
