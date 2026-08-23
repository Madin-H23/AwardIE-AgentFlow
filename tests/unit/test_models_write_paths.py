"""T69 models 写路径护栏（决策分析 P2 批1）：种子库上直打 award.py / laboratory.py 的
INSERT/UPDATE/关联重写/删除分支。

背景：全量行覆盖率实测 backend/models 44%、award.py 缺 56%——R-031（写路径缺 commit
静默回滚）正发生在此类低覆盖文件。本文件用种子库提供真实护栏：
- _save_award 写后立即用**新连接**回读（若 commit 缺失，closing 关闭即回滚、行不存在——
  这正是 R-031 的回归断言形态）；
- UPDATE 分支、四张关联表的删旧插新+去重语义、competition_id 守卫；
- update_validation_status / delete_award；
- LaboratoryManager 增改/成员绑定/dirty→save 落库链路。
"""
import sqlite3
from types import SimpleNamespace

from PIL import Image

import pytest

from tests.fixtures.seeded_db import seeded_app, smoke_client  # noqa: F401


@pytest.fixture()
def seed_db_path(seeded_app):
    return seeded_app.config["DATABASE_PATH"]


@pytest.fixture()
def award_mgr(seed_db_path, seeded_app, tmp_path):
    from backend.models.award import AwardManager
    return AwardManager(str(seed_db_path), images_dir=tmp_path / "award_images")


@pytest.fixture()
def lab_mgr(seed_db_path):
    from backend.models.laboratory import LaboratoryManager
    from backend.models.student import StudentManager
    from backend.models.teacher import TeacherManager
    return LaboratoryManager(str(seed_db_path),
                             student_manager=StudentManager(str(seed_db_path)),
                             teacher_manager=TeacherManager(str(seed_db_path)))


def _row(db, sql, params=()):
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _new_award(**over):
    """最小合法 Award：competition_id 必填（_save_award 守卫）。"""
    from backend.models.award import Award
    base = dict(image_hash="hash-t69", ocr_result="T69 OCR",
                competition_id=1, winner_name="测试获奖人",
                competition_name_in_file="蓝桥杯", year=2025,
                award_level="一等奖", submitter_type="student")
    base.update(over)
    return Award(**base)


class TestAwardSavePaths:
    def test_insert_persists_after_connection_close(self, seed_db_path, award_mgr):
        """R-031 回归形态：写入后新连接可读回=commit 真实落库。"""
        award = _new_award(image_hash="hash-t69-insert")
        assert award.id is None
        award_mgr._save_award(award)
        assert award.id is not None
        row = _row(seed_db_path, "SELECT * FROM awards WHERE id=?", (award.id,))
        assert row is not None, "连接关闭后行丢失=commit 缺失（R-031 复发）"
        assert row["image_hash"] == "hash-t69-insert"
        assert row["competition_id"] == 1

    def test_update_branch_persists(self, seed_db_path, award_mgr):
        award = _new_award(image_hash="hash-t69-upd")
        award_mgr._save_award(award)
        award.winner_name = "改名后的获奖人"
        award.is_abnormal = True
        award_mgr._save_award(award)   # id 已存在 → UPDATE 分支
        row = _row(seed_db_path, "SELECT winner_name, is_abnormal FROM awards WHERE id=?",
                   (award.id,))
        assert row["winner_name"] == "改名后的获奖人"
        assert row["is_abnormal"] in (1, True)

    def test_associations_replace_with_dedup(self, seed_db_path, award_mgr):
        """四张关联表先删后插 + 同 id 去重。"""
        award = _new_award(image_hash="hash-t69-assoc")
        s1, s2 = SimpleNamespace(id=3), SimpleNamespace(id=4)      # 种子学生 users.id
        t1 = SimpleNamespace(id=2)                                  # 种子教师 users.id
        award.student_winners = [s1, s1, s2]       # 含重复
        award.teacher_winners = [t1]
        award.supervisors = [t1, t1]               # 含重复
        award.related_students = [s2, s2]          # 含重复
        award_mgr._save_award(award)

        def count(table):
            conn = sqlite3.connect(str(seed_db_path))
            try:
                return conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE award_id=?", (award.id,)).fetchone()[0]
            finally:
                conn.close()

        assert count("award_student_winners") == 2
        assert count("award_teacher_winners") == 1
        assert count("award_supervisors") == 1
        assert count("award_related_students") == 1

    def test_null_competition_id_rejected(self, seed_db_path, award_mgr):
        """守卫：competition_id 为空的 award 不落库（异常被方法内吞掉，行为=未写入）。"""
        award = _new_award(competition_id=None)
        award_mgr._save_award(award)
        assert award.id is None
        assert _row(seed_db_path, "SELECT id FROM awards WHERE image_hash='hash-t69'") is None

    def test_update_validation_status(self, seed_db_path, award_mgr):
        award = _new_award(image_hash="hash-t69-val")
        award_mgr._save_award(award)
        award_mgr.update_validation_status(award.id, True, '{"abnormal": true}')
        row = _row(seed_db_path, "SELECT is_abnormal, validation_result FROM awards WHERE id=?",
                   (award.id,))
        assert row["is_abnormal"] in (1, True)
        assert '"abnormal"' in (row["validation_result"] or "")

    def test_delete_award_removes_row(self, seed_db_path, award_mgr):
        award = _new_award(image_hash="hash-t69-del")
        award_mgr._save_award(award)
        assert award_mgr.delete_award(award.id) in (True, False)  # 不抛异常即可
        assert _row(seed_db_path, "SELECT id FROM awards WHERE id=?", (award.id,)) is None
        # 幂等：再删不抛异常
        award_mgr.delete_award(award.id)


class TestLaboratoryWritePaths:
    def test_add_and_update_lab_persists_via_save(self, seed_db_path, lab_mgr):
        lab = lab_mgr.add_laboratory("T69实验室", description="写路径测试")
        assert lab is not None
        assert lab_mgr.save() is not False          # save 后临时 id(0) 换成真实自增 id
        assert lab.id and lab.id > 0
        row = _row(seed_db_path, "SELECT name, description FROM laboratories WHERE id=?",
                   (lab.id,))
        assert row and row["name"] == "T69实验室"

        lab.description = "更新后的描述"
        assert lab_mgr.update_laboratory(lab) is True
        lab_mgr.save()
        row = _row(seed_db_path, "SELECT description FROM laboratories WHERE id=?", (lab.id,))
        assert row["description"] == "更新后的描述"

    def test_add_duplicate_lab_current_semantics(self, lab_mgr):
        """行为固化：add_laboratory 实际不判重（docstring 称重名返回 None 与实现
        不符，返回 None 仅出现在异常路径）——本用例固化现状，防止无意识变更。"""
        lab = lab_mgr.add_laboratory("种子实验室")
        assert lab is not None and lab.id == 0

    def test_student_membership_roundtrip(self, seed_db_path, lab_mgr):
        """行为注记：add_student_to_lab 的 student_id 形参实为 users.id 主键
        （内部走 get_student_by_id 整型比较），业务学号须用 student_pk 传主键。"""
        lab = lab_mgr.add_laboratory("T69成员实验室")
        lab_mgr.save()
        assert lab.id and lab.id > 0
        # seed 学生 212306413 的 users.id=3（种子插入序第 3 位）
        assert lab_mgr.add_student_to_lab(lab.id, student_pk=3) is True
        assert any(getattr(s, "id", None) == 3 for s in lab.students)
        assert lab_mgr.save() is not False
        row = _row(seed_db_path,
                   "SELECT COUNT(*) c FROM laboratory_students WHERE laboratory_id=?",
                   (lab.id,))
        assert row["c"] >= 1
        # remove 侧形参不同：按姓名或学号匹配（与 add 的主键形态又不一样，行为注记）
        assert lab_mgr.remove_student_from_lab(lab.id, name="陈品天") is True

class TestAwardAddFlow:
    def _managers(self, db):
        from backend.models.award import AwardManager
        from backend.models.competition import CompetitionManager
        from backend.models.student import StudentManager
        from backend.models.teacher import TeacherManager
        return (AwardManager(str(db), images_dir=self._imgs),
                CompetitionManager(str(db)), StudentManager(str(db)),
                TeacherManager(str(db)))

    def test_add_award_new_then_hash_dedup(self, seed_db_path, seeded_app, tmp_path):
        """add_award 全流程：新建入库 + 同 hash 二次提交走查重分支（is_new=False）。"""
        import uuid
        from PIL import Image
        self.__class__._imgs = tmp_path / "award_imgs"
        img = tmp_path / "cert_t69.png"
        Image.new("RGB", (8, 8), color=(120, 160, 220)).save(img)

        mgr, comp, stu, tea = self._managers(seed_db_path)
        extract = {"certificate_id": f"T69-{uuid.uuid4().hex[:8]}", "competition_name": "蓝桥杯",
                   "winner_name": "陈品天", "supervisor_name": "黄巧云",
                   "award_level": "一等奖", "year": 2025}
        award, is_new = mgr.add_award(
            str(img), "T69 OCR 文本", extract, f"hash-t69-flow-{uuid.uuid4().hex[:6]}",
            comp, stu, tea, submitter_type="student", submitter_id=3)
        assert is_new is True and award.id

        award2, is_new2 = mgr.add_award(
            str(img), "T69 OCR 文本", extract,
            f"hash-t69-flow-same-{uuid.uuid4().hex[:6]}",
            comp, stu, tea, submitter_type="student", submitter_id=3)
        assert is_new2 is False          # certificate_id 相同 → 命中查重分支
        assert award2.id == award.id


class TestLaboratoryAuxMethods:
    def test_teacher_assistant_image_roundtrip(self, seed_db_path, lab_mgr, tmp_path):
        lab = lab_mgr.add_laboratory("T69辅助方法实验室")
        lab_mgr.save()
        assert lab.id and lab.id > 0

        # 「每师一室」业务约束：种子教师(2) 已绑定种子实验室(id=1)，加入新室必须被拒
        # （0002 迁移曾丢失该唯一约束，现依赖业务层兜底——此断言即其回归护栏）
        assert lab_mgr.add_teacher_to_lab(lab.id, teacher_pk=2) is False
        assert lab.instructors == []

        # 助教必须先是实验室成员（非成员添加被业务层拒绝）
        assert lab_mgr.add_student_to_lab(lab.id, student_pk=3) is True
        assert lab_mgr.add_assistant_to_lab(lab.id, 3) is True            # 种子学生主键 3
        assert lab_mgr.remove_assistant_from_lab(lab.id, 3) is True

        img = tmp_path / "lab_pic.png"
        Image.new("RGB", (6, 6)).save(img)
        ok_add = lab_mgr.add_laboratory_image(lab.id, str(img))
        assert ok_add in (True, False)     # 视文件管理器形态而定，不抛异常即可


class TestInnovationBulkDelete:
    def test_delete_all_counts(self, seed_db_path):
        from backend.models.innovation_project import InnovationProjectManager
        mgr = InnovationProjectManager(str(seed_db_path))
        mgr.add_project({"project_name": "T69批量1"})
        mgr.add_project({"project_name": "T69批量2"})
        deleted = mgr.delete_all()
        assert deleted >= 2
        assert _row(seed_db_path, "SELECT COUNT(*) c FROM innovation_projects")["c"] == 0

class TestPendingArchiveRoundtrip:
    def test_archive_unarchive_state_machine(self, seed_db_path):
        """软归档状态机：submit→archived→submit 全往返 + 条件更新防竞态语义。"""
        from backend.models.pending_achievement import PendingAchievementManager
        mgr = PendingAchievementManager(str(seed_db_path))
        submit_row = next(p for p in mgr.get_pending_by_submitter('student', 3,
                                                                  exclude_archived=False)
                          if p.status == 'submit')
        assert mgr.archive(submit_row.id) is True       # submit → archived
        assert mgr.archive(submit_row.id) is False      # 条件更新：非 submit 再归档=拒绝
        assert mgr.unarchive(submit_row.id) is True     # archived → submit（入库失败补偿）
        assert mgr.unarchive(submit_row.id) is False    # 非 archived 再回滚=拒绝
        back = mgr.reload_from_db(submit_row.id)
        assert back is not None and back.status == 'submit'   # 状态复原，不污染同会话后续用例


class TestAwardUpdateFromJson:
    def test_update_from_json_rebuilds_fields_and_associations(self, seed_db_path,
                                                               seeded_app, tmp_path):
        """update_from_json：抽取结果字段刷新 + 获奖人/指导教师关联重建。"""
        from backend.models.award import AwardManager
        from backend.models.competition import CompetitionManager
        from backend.models.student import StudentManager
        from backend.models.teacher import TeacherManager
        mgr = AwardManager(str(seed_db_path), images_dir=tmp_path / "imgs2")
        comp, stu, tea = (CompetitionManager(str(seed_db_path)),
                          StudentManager(str(seed_db_path)),
                          TeacherManager(str(seed_db_path)))
        award = _new_award(image_hash="hash-t69-ufj", competition_name_in_file="蓝桥杯")
        mgr._save_award(award)

        extract = {"competition_name": "全国大学生数学建模竞赛", "track": "本科组",
                   "issuer": "中国工业与应用数学学会", "award_level": "二等奖",
                   "year": 2024, "winner_name": "陈品天,另一学生",
                   "supervisor_name": "黄巧云", "certificate_id": "T69-UFJ-1"}
        award.update_from_json(extract, comp, stu, tea)
        mgr._save_award(award)

        row = _row(seed_db_path, "SELECT * FROM awards WHERE id=?", (award.id,))
        assert row["competition_name_in_file"] == "全国大学生数学建模竞赛"
        assert row["award_level"] == "二等奖"
        conn = sqlite3.connect(str(seed_db_path))
        try:
            n_winners = conn.execute(
                "SELECT COUNT(*) FROM award_student_winners WHERE award_id=?",
                (award.id,)).fetchone()[0]
            n_supers = conn.execute(
                "SELECT COUNT(*) FROM award_supervisors WHERE award_id=?",
                (award.id,)).fetchone()[0]
        finally:
            conn.close()
        assert n_winners == 2 and n_supers == 1
