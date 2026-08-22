"""LogAnalyzer：日志聚合统计引擎（阶段六 L3，日志系统设计 §4.4）。

只读聚合：动作分布/错误趋势/审核瓶颈/活跃度/AI 健康/留痕健康/每日摘要。
数据源：achievement_audit_log / system_event_log / pending_achievements / metrics。
"""
from datetime import date, datetime, timedelta

from backend.utils.db_connection import get_connection


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


class LogAnalyzer:
    """日志统计分析引擎（只读）。"""

    _db_path = None

    @classmethod
    def _get_db_path(cls):
        if cls._db_path is None:
            from config.loader import ConfigLoader
            cls._db_path = str(ConfigLoader().get_path('database', 'competitions_db'))
        return cls._db_path

    # ---------- 审核动作分布 ----------
    @staticmethod
    def action_distribution(start_date=None, end_date=None, db_path=None) -> dict:
        """audit_log action_type 分组计数：{action_type: count}。"""
        where, params = [], []
        where.append("COALESCE(is_redundant,0)=0")   # 默认排除重复删除留痕（0009）
        where.append("COALESCE(is_test,0)=0")        # 默认排除测试噪音（0012）
        if start_date:
            where.append("created_at>=?"); params.append(start_date)
        if end_date:
            where.append("created_at<=?"); params.append(end_date)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        conn = get_connection(db_path or LogAnalyzer._get_db_path())
        try:
            rows = conn.execute(f"SELECT action_type, COUNT(*) FROM achievement_audit_log {w} "
                                "GROUP BY action_type", params).fetchall()
            return {r[0]: r[1] for r in rows}
        finally:
            conn.close()

    # ---------- 错误趋势 ----------
    @staticmethod
    def error_trend(days: int = 7, db_path=None) -> list[dict]:
        """system_event_log error/warning 按日分组：[{date, error, warning}]。

        窗口基准用 UTC——system_event_log.created_at 为 SQLite CURRENT_TIMESTAMP（UTC），
        用本地时间过滤会因时差把新记录全部滤掉（L2 教训①变体，实测踩坑）。
        """
        conn = get_connection(db_path or LogAnalyzer._get_db_path())
        try:
            since = ((datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"))
            rows = conn.execute(
                """SELECT substr(created_at, 1, 10) d, event_level, COUNT(*)
                   FROM system_event_log
                   WHERE event_level IN ('error','warning') AND created_at >= ?
                   GROUP BY d, event_level ORDER BY d""",
                (since,)).fetchall()
            trend = {}
            for d, level, n in rows:
                trend.setdefault(d, {"date": d, "error": 0, "warning": 0})[level] = n
            return sorted(trend.values(), key=lambda x: x["date"])
        except Exception:   # 缺表（老库）——空趋势
            return []
        finally:
            conn.close()

    # ---------- 审核瓶颈 ----------
    @staticmethod
    def review_bottleneck(db_path=None) -> dict:
        """待审核积压：{pending_total, over_48h, avg_wait_hours, max_wait_hours}。

        口径：status='submit'（已提交待审核）；等待时长 = now - submit_time。
        """
        conn = get_connection(db_path or LogAnalyzer._get_db_path())
        try:
            row = conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN julianday('now') - julianday(submit_time) > 2 THEN 1 ELSE 0 END),
                          AVG(julianday('now') - julianday(submit_time)) * 24,
                          MAX(julianday('now') - julianday(submit_time)) * 24
                   FROM pending_achievements WHERE status='submit' AND submit_time IS NOT NULL"""
            ).fetchone()
            total = row[0] or 0
            return {"pending_total": total, "over_48h": row[1] or 0,
                    "avg_wait_hours": round(row[2] or 0, 1), "max_wait_hours": round(row[3] or 0, 1)}
        finally:
            conn.close()

    # ---------- 活跃用户 ----------
    @staticmethod
    def user_activity(top_n: int = 10, db_path=None) -> list[dict]:
        """audit_log operator 分组 Top N：[{operator_code, operator_name, count}]。"""
        conn = get_connection(db_path or LogAnalyzer._get_db_path())
        try:
            rows = conn.execute(
                """SELECT operator_code, operator_name, COUNT(*) c
                   FROM achievement_audit_log
                   WHERE operator_code IS NOT NULL AND COALESCE(is_test,0)=0
                   GROUP BY operator_code ORDER BY c DESC LIMIT ?""", (top_n,)).fetchall()
            return [{"operator_code": r[0], "operator_name": r[1], "count": r[2]} for r in rows]
        finally:
            conn.close()

    # ---------- AI 服务健康 ----------
    @staticmethod
    def ai_health() -> dict:
        """熔断状态 + LLM 调用成功率（metrics 计数器）。"""
        out = {"breakers": {}, "llm_success_rate": None}
        try:
            from backend.utils.circuit_breaker import CircuitBreaker
            for name in ("llm", "ocr"):
                out["breakers"][name] = CircuitBreaker.get(name).state
        except Exception:
            pass
        try:
            from backend.services.metrics_snapshot import collect
            snap = collect()
            # collect() 键含 provider 维度；prometheus 0.26 下名字已含 _total 的 Counter
            # sample.name 不再追加 _total（llm_call_total{...}），且会生成 *_created 元数据键——
            # 按 outcome 前缀匹配并排除 created，跨 provider 聚合
            ok = fail = 0
            for k, v in snap.items():
                if k.startswith("llm_call_total") and not k.startswith("llm_call_created"):
                    if "outcome=ok" in k:
                        ok += v
                    elif "outcome=fail" in k:
                        fail += v
            if ok or fail:
                out["llm_success_rate"] = round(ok / (ok + fail), 4)
        except Exception:
            pass
        return out

    # ---------- 留痕写入健康 ----------
    @staticmethod
    def audit_write_health() -> dict:
        """留痕成功率（metrics.audit_write_total ok/fail 推算）。"""
        try:
            from backend.services.metrics_snapshot import collect
            snap = collect()
            ok = snap.get("audit_write_total_total{result=ok}")
            fail = snap.get("audit_write_total_total{result=fail}")
            total = (ok or 0) + (fail or 0)
            return {"total": total, "failure_rate": round((fail or 0) / total, 4) if total else 0.0}
        except Exception:
            return {"total": 0, "failure_rate": 0.0}

    # ---------- 每日摘要 ----------
    @staticmethod
    def daily_summary(day: str = None, db_path=None) -> dict:
        """指定日期（YYYY-MM-DD，默认今天）全量摘要。"""
        day = day or date.today().isoformat()
        start, end = f"{day} 00:00:00", f"{day} 23:59:59"
        conn = get_connection(db_path or LogAnalyzer._get_db_path())
        try:
            audit_n = conn.execute("SELECT COUNT(*) FROM achievement_audit_log "
                                   "WHERE created_at BETWEEN ? AND ? AND COALESCE(is_test,0)=0",
                                   (start, end)).fetchone()[0]
            err_n = sys_n = 0
            try:
                err_n = conn.execute("SELECT COUNT(*) FROM system_event_log "
                                     "WHERE event_level='error' AND created_at BETWEEN ? AND ?",
                                     (start, end)).fetchone()[0]
                sys_n = conn.execute("SELECT COUNT(*) FROM system_event_log "
                                     "WHERE created_at BETWEEN ? AND ?", (start, end)).fetchone()[0]
            except Exception:   # 缺表（老库）——0
                pass
            return {"date": day, "audit_actions": audit_n,
                    "system_events": sys_n, "system_errors": err_n}
        finally:
            conn.close()
