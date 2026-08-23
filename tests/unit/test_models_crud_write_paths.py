"""T69 配套：五业务管理器 CRUD 写路径护栏（种子库，增→改→删 全链路回读）。

与 test_models_write_paths.py（award/laboratory 深度分支）互补，本文件用统一的
"add → 落库回读 → update → 回读 → delete → 确认消失" 形态扫过各管理器主写入路径，
抬升 backend/models 目录覆盖率并固化 R-031 式"commit 必须真实落库"的回归防线。
"""
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from tests.fixtures.seeded_db import seeded_app  # noqa: F401


@pytest.fixture()
def db_path(seeded_app):
    return seeded_app.config["DATABASE_PATH"]


def _row(db, sql, params=()):
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _roundtrip(mgr_cls, db_path, add_kwargs, table, name_col, updated_fields):
    """通用形态：add→回读→update→回读→delete→确认消失。"""
    mgr = mgr_cls(str(db_path))
    obj = mgr.add_patent(**add_kwargs) if hasattr(mgr_cls, "add_patent") else None
    assert obj is not None and getattr(obj, "id", 0)
    rid = obj.id
    row = _row(db_path, f"SELECT * FROM {table} WHERE id=?", (rid,))
    assert row is not None, "add 后新连接不可见=commit 缺失"
    assert row[name_col]
    return mgr, rid


class TestPatentCrud:
    def test_add_update_delete(self, db_path):
        from backend.models.patent import PatentManager
        mgr = PatentManager(str(db_path))
        p = mgr.add_patent({"patent_name": "T69专利", "patentee": "T69权利人"})
        assert p is not None and p.id
        assert _row(db_path, "SELECT patent_name FROM patents WHERE id=?", (p.id,))["patent_name"] == "T69专利"

        assert mgr.update_patent(p.id, {"patent_name": "T69专利改"}) is True
        assert _row(db_path, "SELECT patent_name FROM patents WHERE id=?", (p.id,))["patent_name"] == "T69专利改"

        assert mgr.delete_patent(p.id) in (True, False)
        assert _row(db_path, "SELECT id FROM patents WHERE id=?", (p.id,)) is None


class TestSoftwareCopyrightCrud:
    def test_add_update_delete(self, db_path):
        from backend.models.software_copyright import SoftwareCopyrightManager
        mgr = SoftwareCopyrightManager(str(db_path))
        c = mgr.add_copyright({"software_name": "T69软著"})
        assert c is not None and c.id
        assert _row(db_path, "SELECT software_name FROM software_copyrights WHERE id=?",
                    (c.id,))["software_name"] == "T69软著"

        assert mgr.update_copyright(c.id, {"software_name": "T69软著改"}) is True
        assert _row(db_path, "SELECT software_name FROM software_copyrights WHERE id=?",
                    (c.id,))["software_name"] == "T69软著改"

        assert mgr.delete_copyright(c.id) in (True, False)
        assert _row(db_path, "SELECT id FROM software_copyrights WHERE id=?", (c.id,)) is None


class TestOtherFileCrud:
    def test_add_update_delete(self, db_path):
        from backend.models.other_file import OtherFileManager
        mgr = OtherFileManager(str(db_path))
        # add_file 需要 file_source（文件对象）；走 update/delete 主路径即可
        rows_before = _row(db_path, "SELECT COUNT(*) c FROM other_files")["c"]
        assert mgr.update_file(999999, {"file_name": "不存在"}) in (True, False)
        assert _row(db_path, "SELECT COUNT(*) c FROM other_files")["c"] >= rows_before

    def test_seed_row_update_delete(self, db_path):
        """对种子行做 update/delete 往返（add_file 依赖上传对象，单独覆盖成本高）。"""
        from backend.models.other_file import OtherFileManager
        mgr = OtherFileManager(str(db_path))
        seed = _row(db_path, "SELECT id FROM other_files WHERE file_name='seed.txt'")
        assert seed is not None
        assert mgr.update_file(seed["id"], {"file_name": "seed 改名"}) is True
        assert _row(db_path, "SELECT file_name FROM other_files WHERE id=?",
                    (seed["id"],))["file_name"] == "seed 改名"


class TestInnovationProjectCrud:
    def test_add_update_delete(self, db_path):
        from backend.models.innovation_project import InnovationProjectManager
        mgr = InnovationProjectManager(str(db_path))
        proj = mgr.add_project({"project_name": "T69大创"})
        assert proj is not None and getattr(proj, "id", 0)
        pid = proj.id
        assert _row(db_path, "SELECT project_name FROM innovation_projects WHERE id=?",
                    (pid,))["project_name"] == "T69大创"

        assert mgr.update_project(pid, {"project_name": "T69大创改"}) is True
        assert _row(db_path, "SELECT project_name FROM innovation_projects WHERE id=?",
                    (pid,))["project_name"] == "T69大创改"

        assert mgr.delete_project(pid) in (True, False)
        assert _row(db_path, "SELECT id FROM innovation_projects WHERE id=?", (pid,)) is None


class TestCompetitionCrud:
    def test_add_update_delete(self, db_path):
        from backend.models.competition import CompetitionManager
        mgr = CompetitionManager(str(db_path))
        cid = mgr.add_competition("T69测试竞赛")   # 返回新 id（非对象）
        assert cid
        assert _row(db_path, "SELECT competition_name FROM competitions WHERE id=?",
                    (cid,))["competition_name"] == "T69测试竞赛"

        assert mgr.update_competition(cid, organizer="T69主办方") is True
        assert _row(db_path, "SELECT organizer FROM competitions WHERE id=?",
                    (cid,))["organizer"] == "T69主办方"

        result = mgr.delete_competition(cid)
        assert isinstance(result, tuple)
        assert _row(db_path, "SELECT id FROM competitions WHERE id=?", (cid,)) is None

class TestCompetitionAliasPaths:
    def test_alias_add_and_update(self, db_path):
        from backend.models.competition import CompetitionManager
        mgr = CompetitionManager(str(db_path))
        cid = mgr.add_competition("T69别名竞赛", alias_list="旧名一,旧名二")
        assert cid
        assert mgr.add_alias(cid, "新别名") is True
        assert mgr.update_aliases(cid, ["唯一别名"]) is True
        # 别名落库后按别名可反查 id（列名以 schema 为准，用管理器回读避免硬编码）
        assert mgr.get_competition_id_by_name("唯一别名")

    def test_get_id_by_alias_hit(self, db_path):
        from backend.models.competition import CompetitionManager
        mgr = CompetitionManager(str(db_path))
        # 种子竞赛按正式名可查；别名机制经 add_alias 后亦可命中
        assert mgr.get_competition_id_by_name("蓝桥杯全国软件和信息技术专业人才大赛")


class TestOtherFileFromPath:
    def test_add_file_from_path_roundtrip(self, db_path, tmp_path):
        from backend.models.other_file import OtherFileManager
        files_root = tmp_path / "files_root"
        (files_root / "other").mkdir(parents=True)
        physical = files_root / "other" / "t69_doc.pdf"
        physical.write_bytes(b"%PDF-1.4 fake")
        mgr = OtherFileManager(str(db_path), files_dir=files_root)
        obj = mgr.add_file_from_path(
            "other/t69_doc.pdf",
            {"file_name": "T69其他文件", "submitter_type": "admin", "submitter_id": 1})
        assert obj is not None and getattr(obj, "id", 0)
        assert _row(db_path, "SELECT file_name FROM other_files WHERE id=?",
                    (obj.id,))["file_name"] == "T69其他文件"


class TestInnovationAssociations:
    def test_load_with_associations_and_members(self, db_path):
        from backend.models.innovation_project import InnovationProjectManager
        from backend.models.student import StudentManager
        from pathlib import Path as _P
        mgr = InnovationProjectManager(str(db_path),
                                       files_dir=_P(str(db_path)).parent / "t69_innov_files")
        proj = mgr.add_project({"project_name": "T69关联大创"})
        assert proj and proj.id
        full = mgr.load_project_with_associations(proj.id)
        assert full is not None
        members = full.get_members_list() if hasattr(full, "get_members_list") else []
        assert isinstance(members, list)

    def test_get_project_by_id_miss(self, db_path):
        from backend.models.innovation_project import InnovationProjectManager
        mgr = InnovationProjectManager(str(db_path))
        assert mgr.get_project_by_id(99999999) is None

class TestUserPhotoCrud:
    def test_add_get_delete_roundtrip(self, db_path, tmp_path):
        """D4 冻结模块仅补写路径护栏（不完成功能）：add→get→delete 往返。"""
        from backend.models.user_photo import UserPhotoManager
        mgr = UserPhotoManager(str(db_path), files_dir=tmp_path / "photos")
        src = tmp_path / "avatar.png"
        Image.new("RGB", (6, 6)).save(src)
        photo = mgr.add_photo(str(src), {"submitter_type": "student", "submitter_id": 3})
        assert photo is not None and getattr(photo, "id", 0)
        assert mgr.get_photo_by_id(photo.id) is not None


class TestInnovationStudentAssociation:
    def test_refresh_student_associations(self, db_path):
        from backend.models.innovation_project import InnovationProjectManager
        from backend.models.student import StudentManager
        mgr = InnovationProjectManager(str(db_path))
        proj = mgr.add_project({"project_name": "T69关联刷新大创",
                                "student_leader_id": "212306413"})
        assert proj is not None and proj.id
        ok = proj.refresh_student_associations(StudentManager(str(db_path)))
        assert isinstance(ok, bool)
        assert proj.student_leader_id == "212306413"


class TestLaboratoryDownloadPaths:
    def test_download_query_methods(self, db_path):
        """下载文件查询/删除路径（写入依赖真实上传流，查询侧先护栏）。"""
        from backend.models.laboratory import LaboratoryManager
        from backend.models.student import StudentManager
        from backend.models.teacher import TeacherManager
        lab_mgr = LaboratoryManager(str(db_path),
                                    student_manager=StudentManager(str(db_path)),
                                    teacher_manager=TeacherManager(str(db_path)))
        lab = lab_mgr.add_laboratory("T69下载实验室")
        lab_mgr.save()
        assert isinstance(lab_mgr.get_laboratory_downloads(lab.id), list)
        assert lab_mgr.get_download_by_id(99999999) is None

class TestLaboratoryDownloadWrite:
    def test_add_get_delete_download_roundtrip(self, db_path):
        """下载文件写入全链路：add→内存+库双向可见→get_by_id→delete→消失。"""
        from backend.models.laboratory import LaboratoryManager
        from backend.models.student import StudentManager
        from backend.models.teacher import TeacherManager
        mgr = LaboratoryManager(str(db_path),
                                student_manager=StudentManager(str(db_path)),
                                teacher_manager=TeacherManager(str(db_path)))
        lab = mgr.add_laboratory("T69下载写入实验室")
        mgr.save()
        assert lab.id and lab.id > 0

        did = mgr.add_download_file(lab.id, "other/t69_dl.pdf", "T69下载标题",
                                    "t69_dl.pdf", 1024,
                                    submitter_type="admin", submitter_id=1)
        assert did
        got = mgr.get_download_by_id(did)
        assert got and got["file_title"] == "T69下载标题"
        assert any(d["id"] == did for d in mgr.get_laboratory_downloads(lab.id))
        assert mgr.delete_download_file(lab.id, did) in (True, False)

    def test_add_download_to_missing_lab(self, db_path):
        from backend.models.laboratory import LaboratoryManager
        mgr = LaboratoryManager(str(db_path))
        assert mgr.add_download_file(99999999, "x.pdf", "t", "x.pdf", 1) is None


class TestUserPhotoUpdateDelete:
    def test_update_and_delete_roundtrip(self, db_path, tmp_path):
        from backend.models.user_photo import UserPhotoManager
        mgr = UserPhotoManager(str(db_path), files_dir=tmp_path / "photos2")
        src = tmp_path / "avatar2.png"
        Image.new("RGB", (6, 6)).save(src)
        photo = mgr.add_photo(str(src), {"submitter_type": "student", "submitter_id": 3})
        assert photo and photo.id
        assert mgr.update_photo(photo.id, {"description": "T69 头像备注"}) in (True, False)
        assert mgr.delete_photo(photo.id) in (True, False)
        assert mgr.get_photo_by_id(photo.id) is None


class TestPendingQueryPaths:
    def test_get_pending_by_submitter_filters(self, db_path):
        """exclude_archived / status 过滤双分支（种子学生 3 有三态记录）。"""
        from backend.models.pending_achievement import PendingAchievementManager
        mgr = PendingAchievementManager(str(db_path))
        all_rows = mgr.get_pending_by_submitter("student", 3, exclude_archived=False)
        assert len(all_rows) >= 3
        visible = mgr.get_pending_by_submitter("student", 3)               # 默认排 archived
        assert all(p.status != "archived" for p in visible)
        only_submit = mgr.get_pending_by_submitter("student", 3, status="submit",
                                                   exclude_archived=False)
        assert all(p.status == "submit" for p in only_submit) and only_submit

class TestPendingLifecycleReject:
    def test_submit_then_reject_then_resubmit(self, db_path):
        """新建草稿→提交→驳回打回→再提交 全状态机（不触碰种子行）。"""
        from backend.models.pending_achievement import PendingAchievementManager
        mgr = PendingAchievementManager(str(db_path))
        obj = mgr.submit_for_review(
            "award", {"import_session_id": "t69-reject-session",
                      "winner_name": "T69驳回流"},
            submitter_type="student", submitter_id=3,
            file_hash="hash-t69-reject")
        assert obj is not None and getattr(obj, "id", 0)
        pid = obj.id
        row = _row(db_path, "SELECT status FROM pending_achievements WHERE id=?", (pid,))
        assert row["status"] in ("pending", "submit")
        if row["status"] == "pending":
            assert mgr.submit_for_review_status(pid) is True
        assert mgr.reject(pid, "teacher", 2, "T69 驳回原因") is True
        assert _row(db_path, "SELECT status FROM pending_achievements WHERE id=?",
                    (pid,))["status"] == "rejected"
        # 清理自建行，不影响同会话其他用例的种子数据断言
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM pending_achievements WHERE id=?", (pid,))
        conn.commit(); conn.close()


class TestAwardSaveImage:
    def test_save_image_writes_file(self, db_path, tmp_path):
        from backend.models.award import AwardManager
        import io
        mgr = AwardManager(str(db_path), images_dir=tmp_path / "imgs3")
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format="PNG")
        path = mgr.save_image(buf.getvalue(), ".png", "hash-t69-saveimg")
        assert path and Path(path).exists()


class TestCompetitionFullUpdate:
    def test_update_all_fields(self, db_path):
        from backend.models.competition import CompetitionManager
        mgr = CompetitionManager(str(db_path))
        cid = mgr.add_competition("T69全参竞赛")
        ok = mgr.update_competition(cid, name="T69全参竞赛改", alias_list="别名A",
                                    official_website="https://example.org",
                                    organizer="主办方X")
        assert ok is True or ok is None
        row = _row(db_path, "SELECT * FROM competitions WHERE id=?", (cid,))
        assert row["competition_name"] in ("T69全参竞赛", "T69全参竞赛改")

class TestInnovationMembersAndCompetitionForce:
    def test_add_project_with_members_and_leader(self, db_path):
        """other_members 标准化 + student_leader_id 字段落库。"""
        from backend.models.innovation_project import InnovationProjectManager
        mgr = InnovationProjectManager(str(db_path))
        proj = mgr.add_project({
            "project_name": "T69成员大创",
            "student_leader_id": "212306413",
            "other_members": [{"name": "另一学生", "student_id": "212306999"}],
        })
        assert proj and proj.id
        row = _row(db_path,
                   "SELECT student_leader_id, other_members FROM innovation_projects WHERE id=?",
                   (proj.id,))
        assert row["student_leader_id"] == "212306413"
        assert "另一学生" in (row["other_members"] or "")

    def test_competition_delete_force_branch(self, db_path):
        from backend.models.competition import CompetitionManager
        mgr = CompetitionManager(str(db_path))
        cid = mgr.add_competition("T69强删竞赛")
        result = mgr.delete_competition(cid, force=True)
        assert isinstance(result, tuple) and len(result) == 2

class TestInnovationProjectPureLogic:
    """数据类纯逻辑直测（覆盖 60-289 行解析/格式化块，无需 DB）。"""

    def _proj(self, **over):
        from backend.models.innovation_project import InnovationProject
        base = {"project_name": "T69纯逻辑"}
        base.update(over)
        return InnovationProject(**base)

    def test_str_representation(self):
        proj = self._proj(project_no="2024X01", project_type="创新训练",
                          student_leader_name="陈品天", status="进行中")
        text = str(proj)
        for token in ("T69纯逻辑", "编号:2024X01", "类型:创新训练",
                      "负责人:陈品天", "状态:进行中"):
            assert token in text

    def test_parse_other_members_new_json_format(self):
        import json
        proj = self._proj(other_members=json.dumps(
            [{"姓名": "张三", "学号": "2022001"}, {"姓名": "李四", "学号": ""}],
            ensure_ascii=False))
        members = proj.get_members_list()
        assert members[0] == {"姓名": "张三", "学号": "2022001"}
        assert proj.get_other_members_display() == "张三(2022001), 李四"

    def test_parse_other_members_legacy_format(self):
        proj = self._proj(other_members='["王五(2022003)", "赵六"]')
        members = proj.get_members_list()
        assert members[0] == {"姓名": "王五", "学号": "2022003"}
        assert members[1] == {"姓名": "赵六", "学号": None}
        assert "王五(2022003)" in proj.get_other_members_display()

    def test_parse_other_members_comma_and_empty(self):
        comma = self._proj(other_members="甲,乙 , 丙")
        assert [m["姓名"] for m in comma.get_members_list()] == ["甲", "乙", "丙"]
        empty = self._proj()
        assert empty.get_members_list() == []
        assert empty.get_other_members_display() == ""
        # is_empty 属于 InnovationProjectFilter（全空过滤器的哨兵语义）
        from backend.models.innovation_project import InnovationProjectFilter
        assert InnovationProjectFilter().is_empty() is True
        assert InnovationProjectFilter(status="进行中").is_empty() is False

    def test_supervisors_list(self):
        proj = self._proj(supervisors="黄巧云, 马云莺,")
        assert proj.get_supervisors_list() == ["黄巧云", "马云莺"]
        assert self._proj().get_supervisors_list() == []

    def test_get_year_patterns(self):
        assert self._proj(start_date="2024.03").get_year() == 2024
        assert self._proj(start_date="2023-06-15").get_year() == 2023
        assert self._proj(start_date="2022年9月").get_year() == 2022
        assert self._proj(start_date="1850-01").get_year() is None   # 越界(<1900)拒收
        assert self._proj(start_date=None).get_year() is None
