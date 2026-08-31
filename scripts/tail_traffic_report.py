"""长尾流量周报(#23):解析 nginx access.log,按 v2/v1 分类统计——P3 触发条件可测量化。

触发条件(spec #1):"长尾域月访问量趋零"→ 本脚本给出量化观测。
分类口径:/v2/* 与 /api/v2/* 归 v2;其余归 v1 长尾。

用法:
    python scripts/tail_traffic_report.py                       # 默认日志路径
    python scripts/tail_traffic_report.py --log <access.log>    # 指定日志
"""
import argparse
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_LOG = Path(r"D:\Develop\tools\nginx-win\nginx-1.28.0\logs\access.log")
# nginx 默认 combined:IP - - [time] "METHOD path PROTO" status bytes "ref" "ua"
LINE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3})')


def classify(path: str) -> str:
    if path.startswith("/v2") or path.startswith("/api/v2"):
        return "v2"
    return "v1-长尾"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    log = Path(args.log)
    if not log.exists():
        print(f"日志不存在: {log}")
        sys.exit(1)

    total = Counter()
    status_err = Counter()
    top_paths = Counter()
    first_ts = last_ts = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(line)
        if not m:
            continue
        _, ts, _method, path, status = m.groups()
        total[classify(path)] += 1
        top_paths[path.split("?")[0]] += 1
        if status.startswith("5"):
            status_err[classify(path)] += 1
        if first_ts is None:
            first_ts = ts
        last_ts = ts

    v2, v1 = total.get("v2", 0), total.get("v1-长尾", 0)
    print(f"== 长尾流量报告 ==")
    print(f"日志窗口: {first_ts} ~ {last_ts}")
    print(f"v2 请求(v2//api/v2): {v2}")
    print(f"v1 长尾请求:          {v1}")
    if v2 + v1:
        print(f"v1 长尾占比: {v1 * 100 // (v2 + v1)}%  (P3 触发观测:占比持续 ~0% 且绝对量趋零 → 再评估收束)")
    print(f"5xx: v2={status_err.get('v2', 0)} v1={status_err.get('v1-长尾', 0)}")
    print(f"\nTop {args.top} 路径:")
    for p, n in top_paths.most_common(args.top):
        print(f"  {n:6d}  {p[:90]}")


if __name__ == "__main__":
    main()
