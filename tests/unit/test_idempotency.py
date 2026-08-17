"""T3 回归测试：幂等键存储（多 worker 共享表 + 装饰器复用语义）。"""
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def idem_db(tmp_path, monkeypatch):
    from backend.utils import idempotency as mod
    monkeypatch.setattr(mod, "_DB_PATH", tmp_path / "idem.db")
    return mod


def test_store_and_hit(idem_db):
    assert idem_db.store_response("k1", {"success": True, "n": 1}, 200) is True
    hit = idem_db.get_stored_response("k1")
    assert hit == ({"success": True, "n": 1}, 200)


def test_miss_and_expired(idem_db, monkeypatch):
    assert idem_db.get_stored_response("nope") is None
    idem_db.store_response("k2", {"x": 1}, 200, ttl=-1)      # 立即过期
    assert idem_db.get_stored_response("k2") is None


def test_overwrite_same_key(idem_db):
    idem_db.store_response("k3", {"v": 1}, 200)
    idem_db.store_response("k3", {"v": 2}, 200)              # INSERT OR REPLACE
    assert idem_db.get_stored_response("k3")[0] == {"v": 2}


def test_decorator_returns_cached_and_executes_once():
    from flask import Flask, jsonify
    from backend.utils.idempotency import idempotent
    from backend.utils import idempotency as mod
    app = Flask(__name__)
    app.secret_key = "t"
    calls = {"n": 0}

    @app.route("/batch", methods=["POST"])
    @idempotent(ttl=600)
    def batch():
        calls["n"] += 1
        return jsonify({"done": calls["n"]}), 200

    mod._DB_PATH = None   # 用真实路径会写主库，改临时
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        mod._DB_PATH = Path(td) / "i.db"
        c = app.test_client()
        r1 = c.post("/batch", headers={"X-Idempotency-Key": "abc"})     # 首次执行
        r2 = c.post("/batch", headers={"X-Idempotency-Key": "abc"})     # 命中复用
        assert r1.get_json() == {"done": 1}
        assert r2.get_json() == {"done": 1} and calls["n"] == 1          # 未重复执行
        r3 = c.post("/batch")                                            # 无 key 透传
        assert r3.get_json() == {"done": 2} and calls["n"] == 2


def test_body_key_supported():
    from flask import Flask, jsonify
    from backend.utils.idempotency import idempotent
    from backend.utils import idempotency as mod
    app = Flask(__name__)
    calls = {"n": 0}

    @app.route("/b2", methods=["POST"])
    @idempotent()
    def b2():
        calls["n"] += 1
        return jsonify({"ok": True})

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        mod._DB_PATH = Path(td) / "i2.db"
        c = app.test_client()
        c.post("/b2", json={"idempotency_key": "from-body", "x": 1})
        c.post("/b2", json={"idempotency_key": "from-body", "x": 1})
        assert calls["n"] == 1


def test_batch_routes_decorated():
    """源码防回退：两处批量审核路由必须挂幂等装饰器。"""
    for f in ("app/routes/teacher.py", "app/routes/admin_review.py"):
        src = (PROJECT_ROOT / f).read_text(encoding='utf-8')
        assert '@idempotent' in src, f"{f} 未挂幂等装饰器"
