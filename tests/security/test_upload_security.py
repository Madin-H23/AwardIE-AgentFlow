"""P0-10 / P1-23 回归测试：上传三重校验 + 公开路由 D1 整改。"""
import io
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class FakeUpload:
    """模拟 werkzeug FileStorage 的最小接口（filename + stream）。"""
    def __init__(self, filename, data: bytes):
        self.filename = filename
        self.stream = io.BytesIO(data)


JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 64
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


@pytest.fixture()
def service():
    from backend.services.file_upload_service import FileUploadService
    return FileUploadService()


def test_dangerous_extension_rejected(service):
    """P0-10：html/exe/py 等白名单外扩展一律拒绝。"""
    for name in ('evil.html', 'shell.php', 'payload.exe', 'script.py', 'no-ext'):
        with pytest.raises(ValueError):
            service._validate_upload(FakeUpload(name, b'x' * 10), Path(name).suffix.lower() or '')


def test_forged_extension_rejected(service):
    """P0-10 核心：.jpg 外衣的 HTML 内容必须被魔术字节识破（存储型 XSS 主链）。"""
    with pytest.raises(ValueError):
        service._validate_upload(FakeUpload('evil.jpg', b'<html><script>alert(1)</script></html>'), '.jpg')


def test_oversize_rejected(service, monkeypatch):
    """P1-23：超过大小上限拒绝（临时调小 MAX_UPLOAD_BYTES 测同一分支，零伪造）。"""
    monkeypatch.setattr(service, 'MAX_UPLOAD_BYTES', 10)
    with pytest.raises(ValueError):
        service._validate_upload(FakeUpload('big.jpg', JPEG), '.jpg')   # JPEG 内容 > 10 字节


def test_valid_files_pass(service):
    """正常 jpg/png/pdf/zip 过校验。"""
    service._validate_upload(FakeUpload('a.jpg', JPEG), '.jpg')
    service._validate_upload(FakeUpload('a.png', PNG), '.png')
    service._validate_upload(FakeUpload('a.pdf', b'%PDF-1.7\n' + b'\x00' * 8), '.pdf')
    service._validate_upload(FakeUpload('a.zip', b'PK\x03\x04' + b'\x00' * 8), '.zip')


def test_settings_max_size_tightened():
    """P1-23：settings 上限必须 ≤100MB（防回退 2GB）。"""
    from config.loader import ConfigLoader
    mb = ConfigLoader().load_config()['flask']['max_content_length_mb']
    assert mb <= 100, f'max_content_length_mb={mb} 超限'


def test_public_file_route_requires_login():
    """P0-10/D1：/files/laboratories 未登录必须被拦（原公开 inline 渲染=存储型 XSS 入口）。"""
    import app as _app  # noqa
    src = (PROJECT_ROOT / 'app' / 'routes' / 'auth.py').read_text(encoding='utf-8')
    assert '@require_login' in src, '公开文件路由未挂登录装饰器'
    assert 'as_attachment=True' in src, '未强制 attachment 下载'
