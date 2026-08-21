"""静态资源强缓存回归（app/__init__.py::_static_cache）：
vendor/ 第三方库 7 天 immutable；其余 static 1 小时；非静态路由不得带强缓存。"""
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_vendor_static_long_immutable_cache(client):
    r = client.get('/static/vendor/bootstrap/bootstrap.min.css')
    assert r.status_code == 200
    cc = r.headers.get('Cache-Control', '')
    assert 'max-age=604800' in cc, f'vendor 应 7 天强缓存, 实际: {cc}'
    assert 'immutable' in cc, f'vendor 应 immutable, 实际: {cc}'


def test_own_static_short_cache(client):
    r = client.get('/static/css/tailwind.css')
    assert r.status_code == 200
    cc = r.headers.get('Cache-Control', '')
    assert 'max-age=3600' in cc, f'自有 static 应 1 小时, 实际: {cc}'
    assert 'immutable' not in cc


def test_non_static_no_strong_cache(client):
    r = client.get('/login')
    cc = r.headers.get('Cache-Control', '')
    assert 'max-age=604800' not in cc and 'max-age=3600' not in cc, f'页面路由不应带静态强缓存: {cc}'
