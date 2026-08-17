"""T4 回归测试：AppError 契约——统一包装翻译 / 状态码 / Retry-After。"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.app_error import (AppError, BreakerOpenError,
                                     DuplicateEntryError, NotSubmittableError,
                                     StateConflictError)


@pytest.fixture()
def client():
    from config.flask import TestingConfig
    from app import create_app
    app = create_app(TestingConfig)
    app.config.update(SECRET_KEY="app-error-test-key-0123456789")

    from flask import jsonify

    @app.route("/_t/conflict")
    def _conflict():
        raise StateConflictError("记录已被他人处理，请刷新")

    @app.route("/_t/not-submittable")
    def _ns():
        raise NotSubmittableError()

    @app.route("/_t/dup")
    def _dup():
        raise DuplicateEntryError("重复入库")

    @app.route("/_t/breaker")
    def _brk():
        raise BreakerOpenError(retry_after=77)

    return app.test_client()


def test_conflict_translated(client):
    r = client.get("/_t/conflict")
    body = r.get_json()
    assert r.status_code == 409 and body["code"] == 3001
    assert body["message"] == "记录已被他人处理，请刷新"
    assert set(body) == {"trace_id", "code", "message", "data"}     # 统一包装四件套


def test_not_submittable_default_message(client):
    r = client.get("/_t/not-submittable")
    assert r.get_json()["code"] == 3002 and r.status_code == 409


def test_duplicate(client):
    assert client.get("/_t/dup").get_json()["code"] == 3003


def test_breaker_with_retry_after(client):
    r = client.get("/_t/breaker")
    assert r.status_code == 503
    assert r.get_json()["code"] == 4003
    assert r.headers.get("Retry-After") == "77"                     # CR 4003 附 Retry-After


def test_errorhandler_registered_in_real_app():
    from app import create_app
    from config.flask import TestingConfig
    app = create_app(TestingConfig)
    assert AppError in app.error_handler_spec[None].get(None, {})   # 全局 handler 已注册
