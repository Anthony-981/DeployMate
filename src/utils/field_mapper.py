import re


FIELD_ALIASES = {
    "ip": ["ip", "ip地址", "服务器ip", "管理ip", "管理网ip", "带内管理ip", "ip address", "ip_address"],
    "role": ["角色", "机器角色", "节点角色", "节点类型", "设备类型", "用途", "功能", "role"],
    "business_ip": ["业务网ip", "业务ip", "业务网络ip", "business ip", "business_ip"],
    "cluster_ip": ["集群网ip", "集群ip", "cluster ip", "cluster_ip"],
    "compute_ip": ["计算网ip", "计算ip", "compute ip", "compute_ip"],
    "storage_ip": ["存储网ip", "存储ip", "storage ip", "storage_ip"],
    "hostname": ["主机名", "服务器名称", "设备名称", "节点名称", "hostname", "host name"],
    "os": ["操作系统", "os", "系统"],
    "cpu": ["cpu", "cpu型号", "处理器"],
    "memory": ["内存", "memory", "内存大小"],
    "gpu_count": ["gpu数量", "gpu数", "显卡数量", "gpu count"],
    "gpu_model": ["gpu型号", "显卡型号", "gpu model"],
    "gpu": ["gpu", "显卡"],
    "cuda": ["cuda", "cuda版本"],
    "docker": ["docker", "docker版本"],
    "username": ["用户名", "用户", "账号", "账户", "登录用户", "登录账号", "user", "username"],
    "password": ["密码", "口令", "登录密码", "passwd", "password"],
    "remarks": ["备注", "说明", "remark", "remarks"],
    "sales": ["销售", "销售人员", "销售姓名", "sales"],
    "location": ["地点", "实施地点", "项目地点", "所在地", "location"],
}


def normalize_machine_header(name: str) -> list[str]:
    """Map composite Chinese headers such as '存储+集群网' to machine fields."""
    value = _compact_header(name)
    if "存储" in value and "集群" in value:
        return ["cluster_ip", "storage_ip"]
    if "业务" in value and any(word in value for word in ("ip", "网", "地址")):
        return ["business_ip"]
    if "计算" in value and any(word in value for word in ("ip", "网", "地址")):
        return ["compute_ip"]
    if "存储" in value and any(word in value for word in ("ip", "网", "地址")):
        return ["storage_ip"]
    if "集群" in value and any(word in value for word in ("ip", "网", "地址")):
        return ["cluster_ip"]
    if any(word in value for word in ("管理ip", "管理网ip", "带内管理", "服务器ip", "ip地址")):
        return ["ip"]
    if "gpu" in value or "显卡" in value:
        if any(word in value for word in ("数量", "个数", "块数", "gpu数")):
            return ["gpu_count"]
        if any(word in value for word in ("型号", "类型", "规格")):
            return ["gpu_model"]
    if any(word in value for word in ("节点角色", "节点类型", "设备类型", "机器角色", "用途", "功能")):
        return ["role"]
    if any(word in value for word in ("登录用户", "登录账号", "用户名", "账户")):
        return ["username"]
    if any(word in value for word in ("登录密码", "密码", "口令")):
        return ["password"]
    normalized = normalize_field_name(name)
    return [normalized] if normalized in FIELD_ALIASES else []


def _compact_header(name: str) -> str:
    if name is None:
        return ""
    return re.sub(r"[\s\-_—/\\（）()【】\[\]：:]+", "", str(name).strip().lower())

def normalize_field_name(name: str) -> str:
    if not name:
        return ""
    value = _compact_header(name)
    for canonical, aliases in FIELD_ALIASES.items():
        normalized_aliases = [_compact_header(alias) for alias in aliases]
        if value == _compact_header(canonical) or value in normalized_aliases:
            return canonical
    return value
