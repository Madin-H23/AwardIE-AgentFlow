"""M2 回归：student/teacher 上传链路参数化去重（P3-2）。"""
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestRouteShells:
    def test_student_shell_calls_shared(self):
        src = (PROJECT_ROOT / "app" / "routes" / "student.py").read_text(encoding='utf-8')
        m = re.search(r"def achievement_submit_upload\(\):(.*?)(?=\n@bp\.route)", src, re.S)
        shell = m.group(0)
        assert "shared_achievement_submit_upload" in shell
        assert "shared_achievement_submit_upload(student, 'student', 'student')" in shell
        # 薄壳不应再包含原 300 行逻辑
        assert "FileUploadService()" not in shell
        assert "import_session_id" not in shell

    def test_teacher_shell_calls_shared(self):
        src = (PROJECT_ROOT / "app" / "routes" / "teacher.py").read_text(encoding='utf-8')
        m = re.search(r"def achievement_submit_upload\(\):(.*?)(?=\n@bp\.route)", src, re.S)
        shell = m.group(0)
        assert "shared_achievement_submit_upload(teacher, 'teacher', 'teacher')" in shell
        assert "FileUploadService()" not in shell

    def test_shared_function_parameterized(self):
        src = (PROJECT_ROOT / "app" / "routes" / "user_common.py").read_text(encoding='utf-8')
        assert "def shared_achievement_submit_upload(user_obj, user_type, redirect_bp):" in src
        # 参数化 4 处就位
        assert "user_obj.id" in src and "submitter_type = user_type" in src
        assert "redirect_bp}.achievement_submit_results" in src


class TestSharedBehavior:
    def test_shared_core_rejects_missing_user(self):
        """共享函数：user_obj 为 None 时返回 400（原两版的用户检查语义）。

        需真实 AppContext 上下文（共享函数开头 get_app_context_instance），
        用 create_app + test_request_context 提供。
        """
        from config.flask import TestingConfig
        from app import create_app
        app = create_app(TestingConfig)
        app.config.update(SECRET_KEY="m2-key", TESTING=True)
        from app.routes import user_common as uc
        with app.test_request_context(method="POST"):
            from flask import session
            session["user_id"] = "X"
            resp = uc.shared_achievement_submit_upload(None, "student", "student")
            assert resp[1] == 400
            assert "用户信息不存在" in resp[0].get_json()["message"]

    def test_shared_keeps_core_logic(self):
        """共享函数保留原核心（FileUploadService/实验室解析/进度更新）。"""
        src = (PROJECT_ROOT / "app" / "routes" / "user_common.py").read_text(encoding='utf-8')
        assert "FileUploadService()" in src
        assert "update_progress" in src
        assert "_resolve_laboratory_by_first_supervisor" in src
        assert "get_doc_rec_context" in src
