"""P1-3 回归测试：生产环境弱 SECRET_KEY 必须拒绝启动。"""
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.flask import _is_weak_secret_key, validate_secret_key, ProductionConfig


STRONG = 'a' * 64


@pytest.mark.parametrize("key,weak", [
    (None, True), ('', True),
    ('dev-secret-key-change-in-production', True),   # 源码默认占位
    ('dev-secret-key-for-agent', True),              # .env 曾用值
    ('x' * 16, True),                                 # 过短
    (STRONG, False),
    (os.urandom(32).hex(), False),                    # token_hex(32) 推荐格式
])
def test_weak_detection(key, weak):
    assert _is_weak_secret_key(key or '') is weak


def _with_env(env):
    saved = os.environ.get('FLASK_ENV')
    try:
        if env is None:
            os.environ.pop('FLASK_ENV', None)
        else:
            os.environ['FLASK_ENV'] = env
        yield
    finally:
        if saved is None:
            os.environ.pop('FLASK_ENV', None)
        else:
            os.environ['FLASK_ENV'] = saved


def test_production_weak_key_raises():
    for _ in _with_env('production'):
        with pytest.raises(RuntimeError):
            validate_secret_key('dev-secret-key-for-agent')


def test_production_strong_key_passes():
    for _ in _with_env('production'):
        validate_secret_key(STRONG)  # 不抛即通过


def test_dev_weak_key_only_warns():
    for _ in _with_env('development'):
        validate_secret_key('dev-secret-key-for-agent')  # 开发容忍，不抛
