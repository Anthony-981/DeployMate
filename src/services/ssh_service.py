from __future__ import annotations

import re

from src.utils.validators import ValidationError

try:
    import paramiko
except ImportError:  # pragma: no cover - optional until SSH collection is used
    paramiko = None


class SSHService:
    def collect_server_info(self, host: str, username: str, password: str,
                            port: int = 22, timeout: int = 10) -> dict:
        if paramiko is None:
            raise ValidationError("SSH采集需要安装 paramiko 依赖")
        if not host or not username:
            raise ValidationError("SSH主机IP和用户名不能为空")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=host, port=port, username=username,
                           password=password or None, timeout=timeout,
                           auth_timeout=timeout, banner_timeout=timeout)
            gpu_output = self._run_any(client, [
                "nvidia-smi --query-gpu=name --format=csv,noheader",
                "command -v nvidia-smi >/dev/null && nvidia-smi -L | sed 's/^GPU [0-9]*: //'",
            ])
            topo_output = self._run_any(client, ["nvidia-smi topo -m", "nvidia-smi topo -m 2>/dev/null"])
            interface_output = self._run_any(client, [
                "ip -o -4 addr show scope global",
                "ifconfig 2>/dev/null",
                "hostname -I",
            ])
            os_info = self._run_any(client, [
                "grep PRETTY_NAME /etc/os-release | cut -d= -f2-",
                "uname -s -r",
            ])
            return {
                "hostname": self._run(client, "hostname", required=False).strip(),
                "os": os_info.strip().strip('"'),
                "cpu": self._run_any(client, ["nproc", "getconf _NPROCESSORS_ONLN", "sysctl -n hw.ncpu"]).strip(),
                "memory": self._run_any(client, ["free -h | awk '/^Mem:/ {print $2}'", "free -m | awk 'NR==2 {print $2 \" MB\"}'"]).strip(),
                "gpu_count": str(len([line for line in gpu_output.splitlines() if line.strip()])),
                "gpu_model": self._first_gpu_model(gpu_output),
                "gpu": ", ".join(line.strip() for line in gpu_output.splitlines() if line.strip()),
                "gpu_interconnect": self.detect_gpu_interconnect(topo_output) if gpu_output else "",
                "interfaces": self.parse_network_interfaces(interface_output),
            }
        finally:
            client.close()

    @staticmethod
    def _run(client, command: str, required: bool = True) -> str:
        _, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if required and not output:
            error = stderr.read().decode("utf-8", errors="replace").strip()
            raise ValidationError(error or f"SSH命令未返回结果: {command}")
        return output

    @classmethod
    def _run_any(cls, client, commands) -> str:
        for command in commands:
            output = cls._run(client, command, required=False)
            if output:
                return output
        return ""

    @staticmethod
    def _first_gpu_model(output: str) -> str:
        return next((line.strip() for line in output.splitlines() if line.strip()), "")

    @staticmethod
    def detect_gpu_interconnect(topo_output: str) -> str:
        if re.search(r"\bNV(?:LINK|\d*)\b", topo_output or "", re.IGNORECASE):
            return "NVLink"
        if any(token in (topo_output or "") for token in ("PIX", "PXB", "PHB", "SYS")):
            return "PCIe"
        return "PCIe"

    @staticmethod
    def parse_network_interfaces(output: str) -> list[dict]:
        interfaces = []
        seen = set()
        pattern = re.compile(r"^\d+:\s+([^\s:]+)\s+inet\s+(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})\b")
        for line in (output or "").splitlines():
            match = pattern.search(line.strip())
            if not match:
                continue
            name, ip, prefix = match.groups()
            name = name.split("@", 1)[0]
            key = (name, ip)
            if key in seen:
                continue
            seen.add(key)
            interfaces.append({"name": name, "ip": ip, "prefix": int(prefix)})
        if not interfaces:
            for ip in re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", output or ""):
                if not ip.startswith("127.") and all(item["ip"] != ip for item in interfaces):
                    interfaces.append({"name": "unknown", "ip": ip, "prefix": 24})
        return interfaces
