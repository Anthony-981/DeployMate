from __future__ import annotations

import hashlib
import hmac
import secrets

from src.models import User, get_session
from src.utils.validators import ValidationError, optional_text, require_text
from src.services.access_service import current_user_id


class UserService:
    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> str:
        password = str(password or "")
        if not password:
            raise ValidationError("密码不能为空")
        if len(password) > 128:
            raise ValidationError("密码不能超过128个字符")
        if len(password) < 6:
            raise ValidationError("密码至少需要 6 个字符")
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)
        return f"pbkdf2_sha256$180000${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            salt = bytes.fromhex(salt_hex)
            expected = hashlib.pbkdf2_hmac(
                "sha256", str(password).encode("utf-8"), salt, int(rounds)
            ).hex()
            return hmac.compare_digest(expected, digest_hex)
        except (ValueError, TypeError):
            return False

    def has_users(self) -> bool:
        session = get_session()
        try:
            return session.query(User.id).count() > 0
        finally:
            session.close()

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str | None = None,
        role: str = "user",
        actor=None,
    ) -> User:
        if actor is not None and not self.is_admin(actor):
            raise ValidationError("只有系统管理员可以创建用户")
        username = require_text(username, "用户名", 80)
        display_name = optional_text(display_name or username, "显示名称", 100) or username
        if role not in {"admin", "user"}:
            raise ValidationError("用户角色不合法")
        session = get_session()
        try:
            if session.query(User).filter(User.username == username).first():
                raise ValidationError("用户名已存在")
            user = User(
                username=username,
                password_hash=self._hash_password(password),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def authenticate(self, username: str, password: str) -> User | None:
        session = get_session()
        try:
            user = session.query(User).filter(
                User.username == str(username or "").strip(),
                User.is_active.is_(True),
            ).first()
            if not user or not self._verify_password(password, user.password_hash):
                return None
            return user
        finally:
            session.close()

    def change_password(
        self, user_id: int, old_password: str, new_password: str, actor=None
    ) -> User:
        session = get_session()
        try:
            if actor is not None and not self.is_admin(actor) and current_user_id(actor) != int(user_id):
                raise ValidationError("普通用户只能修改自己的账号")
            user = session.query(User).filter(User.id == int(user_id)).first()
            if not user or not self._verify_password(old_password, user.password_hash):
                raise ValidationError("原密码不正确")
            if hmac.compare_digest(str(old_password), str(new_password)):
                raise ValidationError("新密码不能与原密码相同")
            user.password_hash = self._hash_password(new_password)
            session.commit()
            session.refresh(user)
            return user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_user(
        self,
        target_id: int,
        *,
        actor=None,
        username: str | None = None,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        new_password: str | None = None,
    ) -> User:
        """Update an account. Administrators may edit any account; users may edit themselves."""
        if actor is not None and not self.is_admin(actor) and current_user_id(actor) != int(target_id):
            raise ValidationError("普通用户只能修改自己的账号")
        if actor is not None and not self.is_admin(actor) and any(
            value is not None for value in (username, role, is_active)
        ):
            raise ValidationError("普通用户不能修改用户名、角色或启用状态")
        session = get_session()
        try:
            user = session.query(User).filter(User.id == int(target_id)).first()
            if not user:
                raise ValidationError("用户不存在")
            if username is not None:
                username = require_text(username, "用户名", 80)
                duplicate = session.query(User).filter(
                    User.username == username, User.id != user.id
                ).first()
                if duplicate:
                    raise ValidationError("用户名已存在")
                user.username = username
            if display_name is not None:
                user.display_name = optional_text(display_name, "显示名称", 100) or user.username
            if role is not None:
                if role not in {"admin", "user"}:
                    raise ValidationError("用户角色不合法")
                if user.role == "admin" and role != "admin":
                    admins = session.query(User).filter(
                        User.role == "admin", User.is_active.is_(True)
                    ).count()
                    if admins <= 1:
                        raise ValidationError("至少保留一个启用的系统管理员")
                user.role = role
            if is_active is not None:
                if not is_active and user.is_active:
                    active_count = session.query(User).filter(User.is_active.is_(True)).count()
                    if active_count <= 1:
                        raise ValidationError("至少保留一个启用用户")
                    if user.role == "admin":
                        admin_count = session.query(User).filter(
                            User.role == "admin", User.is_active.is_(True)
                        ).count()
                        if admin_count <= 1:
                            raise ValidationError("至少保留一个启用的系统管理员")
                user.is_active = bool(is_active)
            if new_password:
                user.password_hash = self._hash_password(new_password)
            session.commit()
            session.refresh(user)
            return user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_user(self, target_id: int, actor=None) -> None:
        if actor is not None and not self.is_admin(actor):
            raise ValidationError("只有系统管理员可以删除用户")
        if actor is not None and current_user_id(actor) == int(target_id):
            raise ValidationError("不能删除当前登录用户")
        session = get_session()
        try:
            user = session.query(User).filter(User.id == int(target_id)).first()
            if not user:
                raise ValidationError("用户不存在")
            if user.role == "admin" and user.is_active:
                active_admins = session.query(User).filter(
                    User.role == "admin", User.is_active.is_(True)
                ).count()
                if active_admins <= 1:
                    raise ValidationError("至少保留一个启用的系统管理员")
            session.delete(user)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_users(self, actor=None) -> list[User]:
        if actor is not None and not self.is_admin(actor):
            raise ValidationError("只有系统管理员可以查看用户列表")
        session = get_session()
        try:
            return session.query(User).order_by(User.created_at, User.id).all()
        finally:
            session.close()

    def get_user_options(self, actor=None) -> list[tuple[int, str]]:
        return [
            (user.id, f"{user.display_name}（{user.username}）")
            for user in self.list_users(actor=actor)
        ]

    def get_user_label_map(self, user_ids=None, actor=None) -> dict[int, str]:
        if actor is not None and not self.is_admin(actor):
            raise ValidationError("只有系统管理员可以查看用户列表")
        session = get_session()
        try:
            query = session.query(User.id, User.display_name, User.username)
            if user_ids:
                query = query.filter(User.id.in_(set(user_ids)))
            return {
                user_id: f"{display_name}（{username}）"
                for user_id, display_name, username in query.all()
            }
        finally:
            session.close()

    def set_active(self, user_id: int, active: bool, actor=None) -> None:
        if actor is not None and not self.is_admin(actor):
            raise ValidationError("只有系统管理员可以修改用户状态")
        session = get_session()
        try:
            user = session.query(User).filter(User.id == int(user_id)).first()
            if not user:
                raise ValidationError("用户不存在")
            if not active and session.query(User).filter(User.is_active.is_(True)).count() <= 1:
                raise ValidationError("至少保留一个启用用户")
            user.is_active = bool(active)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def is_admin(user) -> bool:
        return bool(user and getattr(user, "role", "user") == "admin")
