"""审核留痕统一入口（P1-13 / 设计 8.6.3——AuditLogger 骨架）。

契约（8.6 定稿决策）：
- append-only：只 INSERT，永不 UPDATE/DELETE
- 不阻塞主业务：独立连接 + 独立事务 + try/except 全吞（失败仅 warning）——best-effort 已声明权衡
- operator 三来源：显式 dict > Flask session > 显式 AI 常量；冗余 code/name 快照避免 join
- trace_id 有则记（请求上下文注入后自动贯通）

action_type 枚举（SRS 附录 D.3）：1=提交 2=AI审核 3=AI通过 4=AI驳回 5=教师复核 6=教师通过
 7=教师驳回 8=入库 9=修改字段 10=删除/放弃 11=撤回
operator_role：1=学生 2=教师 3=AI 4=管理员
"""
import json
import logging

logger = logging.getLogger(__name__)

ROLE_MAP = {"student": 1, "teacher": 2, "admin": 4}
AI_OPERATOR = {"id": None, "code": "AI", "name": "AI智能审核", "role": 3}

# 动作中文标签（单一真源：timeline 端点 / 日志查询展示共用）
ACTION_LABELS = {1: '提交', 2: 'AI 审核', 3: 'AI 通过', 4: 'AI 驳回', 5: '教师复核',
                 6: '审核通过', 7: '驳回打回', 8: '入库', 9: '修改字段', 10: '删除/放弃',
                 11: '撤回', 12: '成果删除'}


def _local_now_str():
    """留痕时间统一存应用本地时间（中国时间）——库内直观可读、排障无换算；
    不用 SQLite CURRENT_TIMESTAMP（恒 UTC）。"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AuditLogger:
    """全生命周期留痕写入器（进程级单例用法：直接调用类方法）。"""

    _db_path = None

    @classmethod
    def _get_db_path(cls):
        if cls._db_path is None:
            from config.loader import ConfigLoader
            cls._db_path = str(ConfigLoader().get_path('database', 'competitions_db'))
        return cls._db_path

    @classmethod
    def _users_display(cls, uid):
        """users.id → (login_code, name)；任何失败返回 None（容错：无表/锁/连接）。"""
        try:
            from backend.utils.db_connection import get_connection
            conn = get_connection(cls._get_db_path())
            try:
                row = conn.execute(
                    "SELECT login_code, name FROM users WHERE id=?", (uid,)).fetchone()
                if row and row[0]:
                    return str(row[0]), (row[1] or str(row[0]))
            finally:
                conn.close()
        except Exception:
            pass
        return None

    @classmethod
    def resolve_display_names(cls, conn, values):
        """把留痕操作人快照值（users.id 或 login_code）解析为 '学号 姓名'。

        历史数据 operator_name/operator_code 形态不一：M1 后曾存 users.id（如 1370），
        更早存业务号（如 02114818）。先按 id 匹配、未命中再按 login_code 匹配；
        解析失败的原值不进返回（调用方回退原快照显示）。conn 须为 sqlite3 连接。
        """
        out = {}
        vals = {str(v) for v in values if v is not None}
        if not vals:
            return out
        try:
            ph = ",".join("?" * len(vals))
            for u in conn.execute(
                    f"SELECT id, login_code, name FROM users WHERE id IN ({ph}) OR login_code IN ({ph})",
                    tuple(vals) + tuple(vals)):
                uid, ucode, uname = u[0], u[1], u[2]   # 位置索引：兼容 row_factory=Row 与默认 tuple
                key = str(uid) if str(uid) in vals else str(ucode)
                if key not in out and ucode:
                    out[key] = f"{ucode} {uname or ucode}".strip()
            return out
        except Exception:
            return out

    @classmethod
    def _resolve_operator(cls, operator=None):
        """显式 dict{code,name,role} 优先；否则尝试 Flask session；AI 用常量。"""
        if operator == "AI":
            return AI_OPERATOR
        if isinstance(operator, dict) and operator.get("code"):
            role = operator.get("role")
            if role is None:
                role = ROLE_MAP.get(operator.get("user_type", ""), 4)
            code = str(operator["code"])
            name = operator.get("name")
            # M1 后调用方多直传 users.id 作 code（name 缺省=数字）——解析回业务号+姓名快照
            if (not name or str(name) == code) and operator.get("id") is not None:
                disp = cls._users_display(operator["id"])
                if disp:
                    code, name = disp
            return {"id": operator.get("id"), "code": code,
                    "name": name or code, "role": role}
        try:  # 请求上下文内自动取当前登录人
            from flask import session
            uid = session.get("user_id")
            if uid:
                ut = session.get("user_type", "")
                return {"id": uid, "code": str(uid), "name": session.get("name", str(uid)),
                        "role": ROLE_MAP.get(ut, 4)}
        except Exception:
            pass
        return None

    @classmethod
    def log(cls, action_type: int, achievement_id, achievement_kind=None, *, operator=None,
            action_result: int = 1, change_detail=None, remark=None, trace_id=None,
            ai_batch_id=None) -> bool:
        """写入一条留痕。任何失败只记 warning，绝不向调用方抛异常（8.6.3 契约）。

        Returns:
            是否写入成功（False=已吞掉的失败，调用方无需处理）。
        """
        try:
            op = cls._resolve_operator(operator)
            if op is None:
                logger.warning("[audit] 缺少 operator，跳过留痕: action=%s achievement=%s",
                               action_type, achievement_id)
                return False
            detail = json.dumps(change_detail, ensure_ascii=False) if change_detail else None
            from backend.utils.db_connection import get_connection
            conn = get_connection(cls._get_db_path())
            try:
                conn.execute(
                    """INSERT INTO achievement_audit_log
                       (achievement_id, achievement_kind, trace_id, action_type, action_result,
                        operator_id, operator_code, operator_name, operator_role,
                        ai_batch_id, change_detail, remark, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (achievement_id, achievement_kind, trace_id, action_type, action_result,
                     op["id"], op["code"], op["name"], op["role"],
                     ai_batch_id, detail, remark, _local_now_str()),
                )
                conn.commit()
                from backend.utils.metrics import inc_audit
                inc_audit(True)
                return True
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001 —— 契约：留痕失败不阻塞主业务
            logger.warning("[audit] 留痕写入失败（已吞掉，不影响主流程）: action=%s achievement=%s err=%s",
                           action_type, achievement_id, e)
            from backend.utils.metrics import inc_audit
            inc_audit(False)
            return False


# 便捷函数（业务代码一行调用）
audit_log = AuditLogger.log
