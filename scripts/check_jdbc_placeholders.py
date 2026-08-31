"""jdbc.update 占位符审计(#24):SQL 文本块 ? 数 vs Java 参数表达式数 三对账。

背景:本次冲刺两连踩(11列9问号+3NOW、8列6问号7参)。集成测试已覆盖五类物化路径,
本脚本做静态补充对账:解析 awardie-backend 源码中 jdbc.update 的三引号文本块 SQL 调用,
对每个调用输出 SQL 内 ? 计数与 Java 顶层参数表达式计数,不一致即列出(含行号)。

用法:python scripts/check_jdbc_placeholders.py   (在 repo 根执行)
"""
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "awardie-backend" / "src" / "main" / "java"
CALL_RE = re.compile(r"jdbc\.update\(")


def split_top_level(text):
    """顶层逗号切分(括号深度内不算)。"""
    items, buf, depth = [], [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf and "".join(buf).strip():
        items.append("".join(buf))
    return [i.strip() for i in items if i.strip()]


def count_slots(sql):
    """INSERT 列数与 VALUES 槽位数;非 INSERT 返回 None。"""
    m = re.search(r"INSERT\s+INTO\s+\S+\s*\(([^)]*)\)\s*VALUES\s*\((.*)\)\s*$", sql.strip(), re.S | re.I)
    if not m:
        return None
    cols = split_top_level(m.group(1))
    slots = split_top_level(m.group(2))
    return len(cols), len(slots)


def extract_calls(text: str, path: Path):
    """扫描 jdbc.update( 调用,产出 (行号, sql占位符数, 参数表达式个数) 列表。"""
    out = []
    for m in CALL_RE.finditer(text):
        start = m.end()
        i = start
        n = len(text)
        # 1) 找 SQL 参数:文本块("""...""")或普通字符串,后随逗号
        sql = None
        while i < n and text[i] in " \t\r\n":
            i += 1
        if text.startswith('"""', i):
            j = text.find('"""', i + 3)
            if j < 0:
                continue
            sql = text[i + 3:j]
            i = j + 3
        else:
            # 普通字符串拼接形式(如 "...": 跳过——本仓库 jdbc.update 均为文本块)
            continue
        # 跳到第一个逗号(顶层)
        while i < n and text[i] != ",":
            if text[i] == ")":  # 无参数调用
                break
            i += 1
        if i >= n or text[i] != ",":
            q = sql.count("?")
            out.append((text[:start].count("\n") + 1, q, 0, path, count_slots(sql)))
            continue
        i += 1
        # 2) 数 Java 顶层参数:括号深度计追到本调用收尾 ")"
        depth = 1  # jdbc.update( 已开
        args = 0
        arg_chars = 0
        in_str = False
        in_tblock = False
        while i < n:
            ch = text[i]
            if in_tblock:
                if text.startswith('"""', i):
                    in_tblock = False
                    i += 3
                    continue
                i += 1
                continue
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
                i += 1
                continue
            if text.startswith('"""', i):
                in_tblock = True
                i += 3
                continue
            if ch == '"':
                in_str = True
                i += 1
                continue
            if ch in "([{":
                depth += 1
                i += 1
                continue
            if ch in ")]}":
                if ch == ")" and depth == 1:
                    # 收尾:若本参数有字符,计一个
                    if arg_chars > 0:
                        args += 1
                    break
                depth -= 1
                i += 1
                continue
            if ch == "," and depth == 1:
                args += 1
                arg_chars = 0
                i += 1
                continue
            if not ch.isspace():
                arg_chars += 1
            i += 1
        q = sql.count("?")
        out.append((text[:start].count("\n") + 1, q, args, path, count_slots(sql)))
    return out


def main():
    violations = []
    checked = 0
    for java in BACKEND.rglob("*.java"):
        text = java.read_text(encoding="utf-8", errors="replace")
        for line_no, q, args, path, slots in extract_calls(text, java):
            checked += 1
            rel = path.relative_to(BACKEND.parents[2])
            if q != args:
                violations.append(f"{rel}:{line_no}: SQL ? 数={q} 但 Java 参数数={args}")
            if slots is not None:
                cols_n, slots_n = slots
                if cols_n != slots_n:
                    violations.append(f"{rel}:{line_no}: INSERT 列数={cols_n} 但 VALUES 槽位数={slots_n}")
    print(f"扫描 jdbc.update 调用 {checked} 处")
    if violations:
        print(f"✗ 占位符/参数不一致 {len(violations)} 处:")
        for v in violations:
            print(" ", v)
        sys.exit(1)
    print("✓ 全部一致(? 数 == Java 参数数)")


if __name__ == "__main__":
    main()
