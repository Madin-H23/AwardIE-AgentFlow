"""users Repository（M1 后半③②：ORM 读路径渐进接管，Manager 退位试点）。

策略：Repository 提供 ORM 读方法，业务调用点逐步切换；原 StudentManager/TeacherManager
保留（写路径与旧表兼容），待旧表视图化后彻底移除。
"""
from typing import Optional

from sqlalchemy import select

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
