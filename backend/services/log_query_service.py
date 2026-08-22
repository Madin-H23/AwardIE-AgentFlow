"""LogQueryService：多源日志统一查询（阶段六 L2，日志系统设计 §4.1）。

只读服务——查询 audit_log / system_event_log / review_logs，跨源合并排序。
不触碰任何写入路径（分层不变量）。
"""
import json

from backend.utils.db_connection import get_connection


def _paginate(items_sql: str, count_sql: str, params: list, page: int, per_page: int,
              conn) -> dict:
    total = conn.execute(count_sql, params).fetchone()[0]
    rows = conn.execute(items_sql + " ORDER BY id DESC LIMIT ? OFFSET ?",
                        params + [per_page, (page - 1) * per_page]).fetchall()
    return {"items": [dict(r) for r in rows], "total": total,
            "page": page, "per_page": per_page}


class LogQueryService:
    """统一日志查询服务（只读）。"""

    _db_path = None

    @classmethod
    def _get_db_path(cls):
        if cls._db_path is None:
            from config.loader import ConfigLoader
            cls._db_path = str(ConfigLoader().get_path('database', 'competitions_db'))
        return cls._db_path

    # ---------- achievement_audit_log ----------
    @staticmethod
    def query_audit_logs(*, page=1, per_page=50, action_type=None, operator_role=None,
                         achievement_id=None, trace_id=None,
                         start_date=None, end_date=None, db_path=None,
                         include_tests=False) -> dict:
        where, params = [], []
        # 去重标记：默认排除重复删除留痕（0009 订正；需看全部可加参数放开）
        where.append("COALESCE(is_redundant,0)=0")
        # 测试噪音：默认排除（0012 打标；include_tests=True 查全量）
        if not include_tests:
            where.append("COALESCE(is_test,0)=0")
        if action_type is not None:
            where.append("action_type=?"); params.append(action_type)
        if operator_role is not None:
            where.append("operator_role=?"); params.append(operator_role)
        if achievement_id is not None:
            where.append("achievement_id=?"); params.append(achievement_id)
        if trace_id:
            where.append("trace_id=?"); params.append(trace_id)
        if start_date:
            where.append("created_at>=?"); params.append(start_date)
        if end_date:
            where.append("created_at<=?"); params.append(end_date)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        conn = get_connection(db_path or LogQueryService._get_db_path())
        try:
            result = _paginate(f"SELECT * FROM achievement_audit_log {w}",
                               f"SELECT COUNT(*) FROM achievement_audit_log {w}",
                               params, page, per_page, conn)
            # 展示加工：动作中文标签 + 操作人显示名（历史数据 operator_name 曾存 users.id 纯数字，
            # 批量解析为 "学号 姓名"；非数字快照原样保留）
            from backend.utils.audit_logger import ACTION_LABELS, AuditLogger
            items = result.get("items") or []
            num_ids = {str(it.get("operator_name")) for it in items
                       if it.get("operator_name") and str(it["operator_name"]).isdigit()}
            disp_map = AuditLogger.resolve_display_names(conn, num_ids)
            for it in items:
                it["action_label"] = ACTION_LABELS.get(it.get("action_type"),
                                                       f"动作{it.get('action_type')}")
                it["operator_display"] = disp_map.get(str(it.get("operator_name")),
                                                      it.get("operator_name") or it.get("operator_code") or "-")
            return result
        finally:
            conn.close()

    # ---------- system_event_log ----------
    @staticmethod
    def _utc_to_local(ts):
        """system_event_log.created_at 为 SQLite CURRENT_TIMESTAMP(UTC)——展示层转本地。
        写入层保持 UTC（90 天清理/每日 09:00 报告窗口依赖该基准，整体评估见数据库结构文档）。"""
        if not ts:
            return ts
        try:
            from datetime import datetime, timezone
            return (datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            return ts

    @staticmethod
    def query_system_events(*, page=1, per_page=50, category=None, level=None,
                            trace_id=None, start_date=None, end_date=None,
                            db_path=None) -> dict:
        where, params = [], []
        if category:
            where.append("event_category=?"); params.append(category)
        if level:
            where.append("event_level=?"); params.append(level)
        if trace_id:
            where.append("trace_id=?"); params.append(trace_id)
        if start_date:
            where.append("created_at>=?"); params.append(start_date)
        if end_date:
            where.append("created_at<=?"); params.append(end_date)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        conn = get_connection(db_path or LogQueryService._get_db_path())
        try:
            result = _paginate(f"SELECT * FROM system_event_log {w}",
                               f"SELECT COUNT(*) FROM system_event_log {w}",
                               params, page, per_page, conn)
            for it in result.get("items") or []:
                it["created_at"] = LogQueryService._utc_to_local(it.get("created_at"))
            return result
        finally:
            conn.close()

    # ---------- review_logs（交叉引用补充） ----------
    @staticmethod
    def query_review_logs(*, page=1, per_page=50, action_type=None, reviewer_id=None,
                          submitter_id=None, start_date=None, end_date=None,
                          db_path=None) -> dict:
        where, params = [], []
        if action_type:
            where.append("action_type=?"); params.append(action_type)
        if reviewer_id is not None:
            where.append("reviewer_id=?"); params.append(reviewer_id)
        if submitter_id is not None:
            where.append("submitter_id=?"); params.append(submitter_id)
        if start_date:
            where.append("created_at>=?"); params.append(start_date)
        if end_date:
            where.append("created_at<=?"); params.append(end_date)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        conn = get_connection(db_path or LogQueryService._get_db_path())
        try:
            return _paginate(f"SELECT * FROM review_logs {w}",
                             f"SELECT COUNT(*) FROM review_logs {w}",
                             params, page, per_page, conn)
        finally:
            conn.close()

    # ---------- 跨源合并 ----------
    @staticmethod
    def query_all(*, source="all", page=1, per_page=50, trace_id=None,
                  start_date=None, end_date=None, db_path=None) -> dict:
        """audit + system_event 按时间合并（review_logs 字段异构大，不并入默认视图）。"""
        db = db_path or LogQueryService._get_db_path()
        rows = []
        if source in ("all", "audit"):
            r = LogQueryService.query_audit_logs(page=1, per_page=500, trace_id=trace_id,
                                                 start_date=start_date, end_date=end_date, db_path=db)
            for it in r["items"]:
                it["_source"] = "audit"
                rows.append(it)
        if source in ("all", "system"):
            r = LogQueryService.query_system_events(page=1, per_page=500, trace_id=trace_id,
                                                    start_date=start_date, end_date=end_date, db_path=db)
            for it in r["items"]:
                it["_source"] = "system"
                rows.append(it)
        rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        total = len(rows)
        start = (page - 1) * per_page
        return {"items": rows[start:start + per_page], "total": total,
                "page": page, "per_page": per_page}
