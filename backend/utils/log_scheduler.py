"""L6 日志定时任务（阶段六收尾，日志系统设计 §8 / 部署 §6）。

后台 daemon 线程，`app/__init__` 启动时挂载：
- 每 5 分钟：MetricsSnapshot.archive()（快照写 system_event_log）
- 每日 09:00 窗口：每日报告留痕（system_event）+ 90 天容量清理 +
  ignored 计划 7 天后重评估置 open
轻量实现（不引 APScheduler）：单线程循环 + 上次日期防重复，daemon 随进程退出。
"""
import threading
import logging
import sys
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_METRICS_INTERVAL = 300          # 5 分钟
_DAILY_HOUR = 9                  # 每日 09:00 窗口
_IGNORED_REOPEN_DAYS = 7
_KEEP_DAYS = 90
_state = {"last_daily": None, "lock": threading.Lock()}


def _metrics_archive():
    try:
        from backend.services.metrics_snapshot import archive
        if archive():
            logger.info("[log_sched] metrics 快照已归档")
    except Exception as e:          # 定时任务不抛出，保证循环存活
        logger.warning("[log_sched] metrics 归档失败: %s", e)


def _cleanup_capacity(db_path):
    """90 天前记录清理（system_event_log + 已解决计划）。"""
    from backend.utils.db_connection import get_connection
    try:
        conn = get_connection(db_path)
        try:
            conn.execute(
                "DELETE FROM system_event_log WHERE created_at < datetime('now', ?)",
                (f"-{_KEEP_DAYS} days",))
            conn.execute(
                "DELETE FROM action_plans WHERE status='resolved' AND resolved_at < datetime('now', ?)",
                (f"-{_KEEP_DAYS} days",))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("[log_sched] 容量清理失败: %s", e)


def _reopen_ignored(db_path):
    """ignored 计划 7 天后重评估（置 open，由下次 evaluate 决定去留）。"""
    from backend.utils.db_connection import get_connection
    try:
        conn = get_connection(db_path)
        try:
            n = conn.execute(
                "UPDATE action_plans SET status='open', updated_at=? "
                "WHERE status='ignored' AND created_at < datetime('now', ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"-{_IGNORED_REOPEN_DAYS} days"))
            conn.commit()
            if n.rowcount:
                logger.info("[log_sched] ignored 计划重评估 %s 条", n.rowcount)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("[log_sched] ignored 重评估失败: %s", e)


def _default_db():
    try:
        from config.loader import get_config
        return get_config()["database"]["competitions_db"]
    except Exception:
        return "database/competitions.db"


def run_daily(db_path=None):
    """每日任务（供定时 + 测试直接调用，幂等防重复由调用方控制）。"""
    db_path = db_path or _default_db()
    _cleanup_capacity(db_path)
    _reopen_ignored(db_path)
    _log_daily_report(db_path)
    _daily_backup()


def _daily_backup():
    """每日全量备份（T63）：复用 scripts/backup.py（三库+chroma+files+.env，
    30 天滚动+WAL checkpoint+对账自检）。失败仅 warning 不影响其余每日任务。
    本地使用场景服务常开，应用内每日备份是主保障；OS 计划任务为可选增强
    （本机 schtasks 交互式任务受安全策略限制无法启动 python，故以应用内为准）。"""
    try:
        import subprocess
        from pathlib import Path
        script = Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
        if not script.exists():
            logger.warning("[log_sched] 备份脚本不存在，跳过每日备份: %s", script)
            return
        r = subprocess.run([sys.executable, str(script)], capture_output=True,
                           text=True, timeout=900)
        if r.returncode == 0:
            logger.info("[log_sched] 每日备份完成")
        else:
            logger.warning("[log_sched] 每日备份返回码 %s: %s",
                           r.returncode, (r.stdout or r.stderr or "")[-300:])
    except Exception as e:
        logger.warning("[log_sched] 每日备份失败: %s", e)


def _log_daily_report(db_path):
    """每日报告摘要写入 system_event_log（category='system'，留痕；推送通道后续接）"""
    try:
        from backend.utils.system_event_logger import SystemEventLogger
        from backend.services.plan_generator import daily_report
        rep = daily_report(db_path=db_path)
        # 键名对齐 LogAnalyzer.daily_summary：audit_actions/system_errors
        SystemEventLogger.log(
            category="system", level="info",
            message=(f"每日报告: 今日actions={rep.get('audit_actions', '?')} "
                     f"错误={rep.get('system_errors', '?')} 告警={len(rep.get('alerts', []))}"),
            source_module="log_scheduler")
    except Exception as e:
        logger.warning("[log_sched] 每日报告留痕失败: %s", e)


def _loop():
    while True:
        try:
            _metrics_archive()
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour >= _DAILY_HOUR and _state["last_daily"] != today:
                # 保证每日仅跑一次
                if _state["lock"].acquire(blocking=False):
                    try:
                        run_daily()
                        _state["last_daily"] = today
                    finally:
                        _state["lock"].release()
        except Exception as e:
            logger.warning("[log_sched] 循环异常: %s", e)
        threading.Event().wait(_METRICS_INTERVAL)


def start():
    """启动后台 daemon 线程（create_app 调用；进程内单例）。"""
    if getattr(_state, "thread", None) and _state["thread"].is_alive():
        return
    t = threading.Thread(target=_loop, name="log-scheduler", daemon=True)
    _state["thread"] = t
    t.start()
    logger.info("[log_sched] 日志定时任务已启动（metrics %ss + 每日 %02d:00）",
                _METRICS_INTERVAL, _DAILY_HOUR)
