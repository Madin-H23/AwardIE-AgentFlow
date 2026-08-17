"""密码强度策略（P2-28 / 2026-08-17 用户定稿规则）。

规则：
1. 长度：普通账号 >8 位（即 ≥9）；管理员账号 ≥12 位。
2. 构成：大写/小写/数字/特殊字符 四类至少出现 3 种（每种至少 1 位）。
3. 键盘安全：不得包含 5 位及以上的键盘连续字符（键盘行/字母序/数字序，正序与倒序均算）。
"""
import re
import secrets
import string

MIN_LENGTH_NORMAL = 9     # "超过 8 位"
MIN_LENGTH_ADMIN = 12
KEYBOARD_RUN_LEN = 5      # 连续 5 位即拒绝

# 键盘行（QWERTY 主三行+数字行）与自然序列；倒序同样禁止
_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "abcdefghijklmnopqrstuvwxyz"]
_FORBIDDEN_RUNS = set()
for _r in _ROWS:
    for _i in range(len(_r) - KEYBOARD_RUN_LEN + 1):
        seg = _r[_i:_i + KEYBOARD_RUN_LEN]
        _FORBIDDEN_RUNS.add(seg)
        _FORBIDDEN_RUNS.add(seg[::-1])

_SPECIAL = "!@#$%^&*()-_=+[]{};:,.<>?/|~"


def _char_class_counts(pwd: str) -> int:
    """四类字符出现的种类数。"""
    classes = [re.search(r"[a-z]", pwd), re.search(r"[A-Z]", pwd),
               re.search(r"\d", pwd), re.search(r"[^a-zA-Z0-9]", pwd)]
    return sum(1 for c in classes if c)


def validate_password_strength(pwd: str, *, is_admin: bool = False) -> tuple[bool, str]:
    """校验密码是否符合策略。

    Returns:
        (ok, message)：ok=False 时 message 说明原因（可直接展示给用户）。
    """
    if not isinstance(pwd, str) or not pwd:
        return False, "密码不能为空"
    min_len = MIN_LENGTH_ADMIN if is_admin else MIN_LENGTH_NORMAL
    if len(pwd) < min_len:
        return False, f"密码长度需超过{'12' if is_admin else '8'}位（当前 {len(pwd)} 位）"
    if _char_class_counts(pwd) < 3:
        return False, "密码需包含大写字母、小写字母、数字、特殊字符中的至少 3 种"
    low = pwd.lower()
    for i in range(len(low) - KEYBOARD_RUN_LEN + 1):
        if low[i:i + KEYBOARD_RUN_LEN] in _FORBIDDEN_RUNS:
            return False, "密码不能包含 5 位及以上的键盘连续字符（如 qwerty、12345 及其倒序）"
    return True, ""


def generate_strong_password(*, is_admin: bool = False) -> str:
    """生成符合策略的随机密码（用于初始/重置密码下发，长度取门槛+3 保证余量）。"""
    length = (MIN_LENGTH_ADMIN if is_admin else MIN_LENGTH_NORMAL) + 3
    alphabet = string.ascii_letters + string.digits + _SPECIAL
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        if _char_class_counts(pwd) >= 3 and validate_password_strength(pwd, is_admin=is_admin)[0]:
            # 随机串极小概率撞键盘序列，validate 兜底重生成
            return pwd
