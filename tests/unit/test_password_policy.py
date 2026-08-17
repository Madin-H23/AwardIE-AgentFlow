"""P2-28 回归测试：密码强度策略（用户定稿规则 2026-08-17）。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.password_policy import (MIN_LENGTH_ADMIN, MIN_LENGTH_NORMAL,
                                 generate_strong_password, validate_password_strength)


def V(pwd, admin=False):
    return validate_password_strength(pwd, is_admin=admin)


class TestLength:
    def test_normal_too_short(self):
        ok, msg = V('Ab1!ab2?')          # 8 位=不超过 8，拒
        assert not ok and '8' in msg

    def test_normal_min_ok(self):
        assert V('Ab1!ab2?z')[0] is True  # 9 位三类

    def test_admin_12_gate(self):
        ok, _ = V('Ab1!ab2?z', admin=True)          # 9 位对管理员不够
        assert not ok
        assert V('Ab1!ab2?zQ9#k', admin=True)[0] is True

    def test_empty_and_none(self):
        assert V('')[0] is False
        assert V(None)[0] is False


class TestCharClasses:
    @pytest.mark.parametrize("pwd", [
        'abcdefghij',      # 仅小写
        'ABCDEFGHIJ',      # 仅大写
        '1234567890',      # 仅数字
        '!!!!!!!!!!',      # 仅特殊
        'abcdef1234',      # 两类
        'ABCdef!!!!',      # 两类
    ])
    def test_below_three_classes_rejected(self, pwd):
        assert V(pwd)[0] is False

    @pytest.mark.parametrize("pwd", ['Ab1!bc2?de', 'aB3cD4!fgh', 'AB12!34ab'])
    def test_three_classes_pass(self, pwd):
        assert V(pwd)[0] is True


class TestKeyboardRuns:
    @pytest.mark.parametrize("pwd", [
        'Qwerty!99',       # 键盘行正序
        '!98765Abc',       # 数字倒序
        'XAsdfg!99',       # 中排正序（大小写混合）
        'Zab9!trewq',      # 键盘行倒序
        'Abcde!99z',       # 字母自然序
        'Ab1!edcba9',      # 字母倒序
    ])
    def test_keyboard_sequence_rejected(self, pwd):
        ok, msg = V(pwd)
        assert not ok and '键盘' in msg

    @pytest.mark.parametrize("pwd", ['Qwer!99ab', 'Ab12!34cd', 'Aq1s2d3f!'])
    def test_short_runs_allowed(self, pwd):
        """4 位以内连续不触发（qwer 是 4 位）。"""
        assert V(pwd)[0] is True


class TestGenerator:
    def test_generated_normal_meets_policy(self):
        for _ in range(50):
            pwd = generate_strong_password()
            assert len(pwd) >= MIN_LENGTH_NORMAL
            assert V(pwd)[0] is True

    def test_generated_admin_meets_policy(self):
        for _ in range(50):
            pwd = generate_strong_password(is_admin=True)
            assert len(pwd) >= MIN_LENGTH_ADMIN
            assert V(pwd, admin=True)[0] is True

    def test_generated_unique(self):
        assert generate_strong_password() != generate_strong_password()
