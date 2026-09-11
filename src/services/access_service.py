from __future__ import annotations

from src.utils.validators import ValidationError


def current_user_id(user) -> int | None:
    value = getattr(user, "id", None)
    return int(value) if value is not None else None


def can_view_all(user) -> bool:
    return user is None or getattr(user, "role", "user") == "admin"


def owner_id_for(user) -> int | None:
    return current_user_id(user)


def scope_query(query, model, user):
    if user is not None and not can_view_all(user):
        user_id = current_user_id(user)
        return query.filter(model.owner_id == user_id) if user_id else query.filter(model.id == -1)
    return query


def require_owned(record, user, action: str = "访问"):
    if user is not None and not can_view_all(user):
        if record is None or getattr(record, "owner_id", None) != current_user_id(user):
            raise ValidationError(f"无权{action}该数据")
    return record
