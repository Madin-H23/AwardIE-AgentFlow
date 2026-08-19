"""users Repository（M1 后半③②：ORM 读路径渐进接管，Manager 退位试点）。

策略：Repository 提供 ORM 读方法，业务调用点逐步切换；原 StudentManager/TeacherManager
保留（写路径与旧表兼容），待旧表视图化后彻底移除。
"""
from typing import Optional

from sqlalchemy import func, select

from backend.orm.base import get_session
from backend.orm.users import User


class UserRepository:
    """users 表 ORM 读仓储（替代旧三表逐查的读路径）。"""

    @staticmethod
    def get_by_login_code(login_code: str) -> Optional[User]:
        s = get_session()
        try:
            return s.execute(select(User).where(User.login_code == login_code)).scalar_one_or_none()
        finally:
            s.close()

    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        s = get_session()
        try:
            return s.get(User, user_id)
        finally:
            s.close()

    @staticmethod
    def list_by_role(role: str) -> list[User]:
        s = get_session()
        try:
            return list(s.execute(select(User).where(User.role == role)).scalars())
        finally:
            s.close()

    # ---- 写路径（M1 后半①：admin 创建/重置/改密切 users 真源）----

    _PROFILE_FIELDS = frozenset({
        "name", "role", "user_activated", "phone", "qq", "skills",
        "profile_is_public", "major", "grade", "title", "department",
        "id_number",
    })

    @staticmethod
    def create_user(login_code: str, name: str, role: str,
                    password_hash: str, needs_password_change: int = 1,
                    **profile) -> int:
        """幂等创建/更新用户行，返回 users.id。

        同 login_code 行已存在时更新其资料字段（幂等，重复提交安全）；
        主键字段（login_code）与白名单外字段一律不写。
        """
        s = get_session()
        try:
            now = func.strftime('%Y-%m-%d %H:%M:%S', 'now')
            u = s.execute(select(User).where(User.login_code == login_code)).scalar_one_or_none()
            if u is None:
                data = {k: v for k, v in profile.items()
                        if k in UserRepository._PROFILE_FIELDS and v is not None}
                u = User(login_code=login_code, name=name, role=role,
                         password_hash=password_hash,
                         needs_password_change=needs_password_change,
                         created_at=now, updated_at=now, **data)
                s.add(u)
            else:
                u.name = name
                u.password_hash = password_hash
                u.needs_password_change = needs_password_change
                for k, v in profile.items():
                    if k in UserRepository._PROFILE_FIELDS and v is not None:
                        setattr(u, k, v)
                u.updated_at = now
            s.commit()
            s.refresh(u)
            return u.id
        finally:
            s.close()

    @staticmethod
    def update_password(login_code: str, password_hash: str,
                        needs_password_change: int = 0) -> int:
        """更新密码与强制改密标记，返回受影响行数（0=无此用户）。"""
        s = get_session()
        try:
            u = s.execute(select(User).where(User.login_code == login_code)).scalar_one_or_none()
            if u is None:
                return 0
            u.password_hash = password_hash
            u.needs_password_change = needs_password_change
            u.updated_at = func.strftime('%Y-%m-%d %H:%M:%S', 'now')
            s.commit()
            return 1
        finally:
            s.close()

    @staticmethod
    def update_profile(login_code: str, **fields) -> int:
        """更新用户资料字段（白名单），返回受影响行数（0=无此用户）。"""
        s = get_session()
        try:
            u = s.execute(select(User).where(User.login_code == login_code)).scalar_one_or_none()
            if u is None:
                return 0
            changed = False
            for k, v in fields.items():
                if k in UserRepository._PROFILE_FIELDS and v is not None:
                    setattr(u, k, v)
                    changed = True
            if changed:
                u.updated_at = func.strftime('%Y-%m-%d %H:%M:%S', 'now')
                s.commit()
            return 1
        finally:
            s.close()
