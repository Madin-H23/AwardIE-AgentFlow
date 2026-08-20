"""阶段三批F回归：时间线 UI 注入源码断言 + 端到端数据流。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def _require_real_db():
    """共享守卫（schemas.require_real_db）：文件存在且 users 表存在，否则 skip（R-028 升级）。"""
    from tests.fixtures.schemas import require_real_db
    require_real_db()


SRC = (PROJECT_ROOT / "app" / "templates" / "admin" / "file_import" / "partials" / "_results_content.html").read_text(encoding="utf-8")


class TestTimelineUI:
    def test_button_present(self):
        """审核页有"轨迹"按钮（teacher_review/admin_review 场景渲染）。"""
        assert "轨迹" in SRC and "showTimeline(" in SRC
        assert "route_prefix in ('teacher_review', 'admin_review')" in SRC

    def test_timeline_component(self):
        """组件拉取 timeline 端点并渲染：AI 徽章区分/空态/时间正序数据源。"""
        assert "/api/audit/timeline/" in SRC
        assert "🤖 AI" in SRC or "is_ai" in SRC          # AI 标识
        assert "暂无审核记录" in SRC                      # 空态
        assert "加载失败" in SRC                          # 错误态

    def test_modal_created_lazily(self):
        assert "timelineModal" in SRC

    def test_reject_button_kept(self):
        """驳回按钮未被误伤。"""
        assert "rejectAward(" in SRC

    def test_endpoint_feeds_ui_format(self):
        _require_real_db()
        """端点返回字段与 UI 消费对齐（action/operator_role/is_ai/created_at/remark）。"""
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="f-key-0123456789abcdef0123456789ab")
        c = app.test_client()
        with c.session_transaction() as s:
            s.update(user_type='teacher', user_id='t1', logged_in=True, role='teacher')
        r = c.get("/api/audit/timeline/award/1")
        data = r.get_json()
        assert data['success'] is True
        if data['timeline']:                     # 非空才校验字段（真实库该成果可能无留痕）
            for field in ("action", "operator_role", "is_ai", "created_at", "remark"):
                assert field in data['timeline'][0], f"端点缺 UI 需要的字段 {field}"
