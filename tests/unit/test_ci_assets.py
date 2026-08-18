"""阶段四批A回归：容器化/CI 资产存在性与关键配置断言。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestDockerAssets:
    def test_dockerfile(self):
        src = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "python:3.11-slim" in src
        assert "requirements-cpu.txt" in src           # CPU 版依赖
        assert "HEALTHCHECK" in src and "/assistant/health" in src
        assert "gunicorn" in src

    def test_compose_dual_instance(self):
        """CR-5：app-api / app-sse 双实例 + Redis（CR-4）。"""
        src = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        assert "app-api" in src and "app-sse" in src
        assert "redis" in src
        assert "5002" in src and "--timeout 300" in src   # SSE 池长超时

    def test_nginx_sse_location(self):
        src = (PROJECT_ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
        assert "/assistant/chat/stream" in src
        assert "proxy_buffering off" in src              # SSE 禁缓冲
        assert "client_max_body_size 100m" in src        # P1-23 对齐


class TestCI:
    def test_ci_pipeline(self):
        src = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "cov-fail-under=70" in src                # CR-3 覆盖率门禁
        assert "pip-audit" in src                        # 依赖扫描
        assert "docker build" in src                     # 构建验证
        # 静态门禁
        assert "sqlite3.connect(self.db_path)" in src    # 禁裸连接 grep
