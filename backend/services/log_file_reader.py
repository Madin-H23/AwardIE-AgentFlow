"""LogFileReader：logs/app.log 读取与解析（阶段六 L2，日志系统设计 §4.2）。

只读服务：tail 尾部 N 行 / search 关键词·级别·时间过滤 / stream 增量监控。
解析格式对齐 run.py（阶段六 L2 起含 [tid:xxx]）：
    2026-08-20 10:00:00 - INFO [app.routes] [tid:abc123] 消息
旧格式（无 tid）兼容解析。
"""
import re
from pathlib import Path

# 新格式（含 tid）优先，旧格式回退
_LOG_PATTERN_TID = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (?P<level>\w+) \[(?P<logger>[\w.]+)\] '
    r'\[tid:(?P<tid>[^\]]*)\] (?P<msg>.*)$')
_LOG_PATTERN_OLD = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (?P<level>\w+) \[(?P<logger>[\w.]+)\] '
    r'(?P<msg>.*)$')


def parse_line(line: str) -> dict | None:
    """解析单行为 {timestamp, level, logger, trace_id, message}；非日志行返回 None（丢弃）。"""
    m = _LOG_PATTERN_TID.match(line) or _LOG_PATTERN_OLD.match(line)
    if not m:
        return None
    d = m.groupdict()
    d["trace_id"] = d.get("tid") or None
    d.pop("tid", None)
    return d


class LogFileReader:
    """应用日志文件读取器（只读）。"""

    _log_path = None

    @classmethod
    def _path(cls) -> Path:
        if cls._log_path is None:
            from config.loader import ConfigLoader
            logs_dir = Path(ConfigLoader().project_root) / 'logs'
            cls._log_path = logs_dir / 'app.log'
        return cls._log_path

    @classmethod
    def tail(cls, lines: int = 100, log_file=None) -> list[dict]:
        """读取最后 N 行（高效倒读），返回解析结果（新→旧顺序）。"""
        path = Path(log_file) if log_file else cls._path()
        if not path.exists():
            return []
        out = []
        with path.open('r', encoding='utf-8', errors='replace') as f:
            for line in reversed(list(f)):      # 小文件（10MB×5 轮转）直接倒序；超大再优化
                parsed = parse_line(line)
                if parsed:
                    out.append(parsed)
                if len(out) >= lines:
                    break
        return out

    @classmethod
    def search(cls, keyword=None, level=None, limit: int = 500,
               start_time=None, end_time=None, log_file=None) -> list[dict]:
        """关键词/级别/时间过滤（旧→新）。时间比较为字符串前缀（ISO 格式可比）。"""
        path = Path(log_file) if log_file else cls._path()
        if not path.exists():
            return []
        kw = (keyword or '').lower()
        results = []
        with path.open('r', encoding='utf-8', errors='replace') as f:
            for line in f:
                parsed = parse_line(line)
                if not parsed or 'raw' in parsed:
                    continue
                if kw and kw not in (parsed['msg'] or '').lower():
                    continue
                if level and parsed['level'] != level:
                    continue
                ts = parsed['ts']
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                results.append(parsed)
                if len(results) >= limit:
                    break
        return results

    @classmethod
    def stream(cls, filter_level=None, filter_keyword=None, log_file=None):
        """增量监控生成器：从当前文件末尾起持续产出新增行（基于 seek position）。

        调用方负责退出（生成器 close）；适合 SSE 接线（L4）。
        """
        import time
        path = Path(log_file) if log_file else cls._path()
        kw = (filter_keyword or '').lower()
        if not path.exists():
            path.touch()
        with path.open('r', encoding='utf-8', errors='replace') as f:
            f.seek(0, 2)   # 跳到末尾，只取新增
            while True:
                line = f.readline()
                if line:
                    parsed = parse_line(line)
                    if parsed and 'raw' not in parsed:
                        if filter_level and parsed['level'] != filter_level:
                            continue
                        if kw and kw not in (parsed['msg'] or '').lower():
                            continue
                        yield parsed
                else:
                    time.sleep(0.5)   # 无新行，稍候（SSE 侧有心跳，无需更密）
