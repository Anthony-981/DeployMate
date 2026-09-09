from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


class ValidationError(ValueError):
    pass


PROJECT_FIELD_LIMITS = {
    "name": 100,
    "customer": 100,
    "project_code": 50,
    "location": 100,
    "sales": 100,
    "remarks": 500,
}

MACHINE_FIELD_LIMITS = {
    "role": 100,
    "ip": 50,
    "business_ip": 50,
    "cluster_ip": 50,
    "compute_ip": 50,
    "storage_ip": 50,
    "hostname": 100,
    "os": 100,
    "cpu": 50,
    "memory": 50,
    "gpu_count": 10,
    "gpu_model": 100,
    "gpu_interconnect": 50,
    "gpu": 100,
    "cuda": 50,
    "docker": 50,
    "username": 50,
    "password": 100,
    "remarks": 500,
}

DAILY_FIELD_LIMITS = {
    "work_content": 2000,
    "problems": 2000,
    "solutions": 2000,
    "next_plan": 2000,
    "remarks": 500,
}

EXPENSE_FIELD_LIMITS = {
    "expense_type": 20,
    "remarks": 200,
}

IPV4_RE = re.compile(r"^(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}$")


def clean_text(value) -> str:
    return "" if value is None else str(value).strip()


def require_text(value, label: str, max_len: int) -> str:
    value = clean_text(value)
    if not value:
        raise ValidationError(f"{label}不能为空")
    if len(value) > max_len:
        raise ValidationError(f"{label}不能超过{max_len}个字符")
    return value


def optional_text(value, label: str, max_len: int) -> str:
    value = clean_text(value)
    if len(value) > max_len:
        raise ValidationError(f"{label}不能超过{max_len}个字符")
    return value


def validate_choice(value, label: str, choices: set[str]) -> str:
    value = clean_text(value)
    if value not in choices:
        raise ValidationError(f"{label}取值不合法")
    return value


def validate_ipv4(value, label: str, required: bool = False) -> str:
    value = clean_text(value)
    if not value:
        if required:
            raise ValidationError(f"{label}不能为空")
        return ""
    if not IPV4_RE.match(value):
        raise ValidationError(f"{label}格式不正确")
    return value


def validate_positive_int_string(value, label: str, max_len: int = 10, required: bool = False) -> str:
    value = clean_text(value)
    if not value:
        if required:
            raise ValidationError(f"{label}不能为空")
        return ""
    if len(value) > max_len or not value.isdigit():
        raise ValidationError(f"{label}必须是正整数，且不能超过{max_len}位")
    return value


def validate_positive_amount(value, label: str):
    value = clean_text(value)
    if not value:
        raise ValidationError(f"{label}不能为空")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f"{label}格式不正确") from exc
    if amount < 0:
        raise ValidationError(f"{label}不能小于0")
    return amount.quantize(Decimal("0.01"))


def validate_date_range(start_date, end_date, start_label: str, end_label: str):
    if start_date and end_date and end_date < start_date:
        raise ValidationError(f"{end_label}不能早于{start_label}")
    return start_date, end_date
