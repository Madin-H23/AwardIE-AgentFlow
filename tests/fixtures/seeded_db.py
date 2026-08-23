"""CI 种子库 fixture（T64）：tmp SQLite 全量 schema + 最小数据集，页面冒烟真跑不 skip。

双路径 patch（缺一即"静默查真实库"事故）：
①app.config['DATABASE_PATH']——多数路由经 current_app.config 读；
②get_config() 返回配置类的 DATABASE_PATH 类属性——auth.py 登录限流/verify_user 直读。
另 patch FILES_DIR（防页面列目录时触碰真实 files/）。
setup/teardown 各调一次 reset_app_context() 复位进程级 _global_app_context
（防真库测试先行初始化后本冒烟静默沿用真实路径）。
"""
import sqlite3
from pathlib import Path

import sys
import pytest

FIXTURES_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FIXTURES_DIR.parents[1]
SCHEMA_SQL = FIXTURES_DIR / "full_schema.sql"

# 三角色样本（与 page_inventory.py 的角色口径一致）
SEED_USERS = [
    # login_code, name, role, title/major 等
    ("admin", "管理员", "admin"),
    ("02110606", "黄巧云", "teacher"),
    ("212306413", "陈品天", "student"),
    ("212306999", "另一学生", "student"),  # 深链越权负例用
]

SEED_COMPETITIONS = [
    # name, white_list
    ("蓝桥杯全国软件和信息技术专业人才大赛", 1),
    ("全国大学生数学建模竞赛", 1),
]


def _build_seeded_db(db_path: Path) -> None:
    """建库：全量 schema + 最小数据集。"""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    cur = conn.cursor()

    for code, name, role in SEED_USERS:
        cur.execute(
            "INSERT INTO users (login_code, name, role) VALUES (?, ?, ?)",
            (code, name, role))

    for name, wl in SEED_COMPETITIONS:
        cur.execute(
            "INSERT INTO competitions (competition_name, white_list) VALUES (?, ?)",
            (name, wl))
    comp_ids = [r[0] for r in cur.execute("SELECT id FROM competitions ORDER BY id")]

    teacher_id = cur.execute(
        "SELECT id FROM users WHERE role='teacher'").fetchone()[0]
    student_id = cur.execute(
        "SELECT id FROM users WHERE role='student' AND login_code='212306413'"
    ).fetchone()[0]
    teacher_users_id = cur.execute(
        "SELECT id FROM users WHERE role='teacher'").fetchone()[0]

    # awards：学生证书×2 + 教师证书×1（教师证书走 award_teacher_winners）
    award_rows = [
        ("hash-student-a", "蓝桥杯", "陈品天", "学生", comp_ids[0], 2025),
        ("hash-student-b", "数学建模", "另一学生", "学生", comp_ids[1], 2024),
        ("hash-teacher-x", "蓝桥杯", "黄巧云", "教师", comp_ids[0], 2025),
    ]
    award_ids = []
    for h, comp_name, winner, role, cid, yr in award_rows:
        cur.execute(
            "INSERT INTO awards (image_hash, winner_name, granted_role,"
            " competition_id, year, submit_time)"
            " VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
            (h, winner, role, cid, yr))
        award_ids.append(cur.lastrowid)
    cur.execute("INSERT INTO award_teacher_winners (award_id, teacher_id) VALUES (?, ?)",
                (award_ids[2], teacher_id))
    cur.execute("INSERT INTO award_student_winners (award_id, student_id) VALUES (?, ?)",
                (award_ids[0], student_id))
    cur.execute("INSERT INTO award_supervisors (award_id, teacher_id) VALUES (?, ?)",
                (award_ids[0], teacher_id))
    cur.execute("INSERT INTO award_related_students (award_id, student_id) VALUES (?, ?)",
                (award_ids[2], student_id))

    # pending_achievements 三态各 1（submit 态带固定 session_id 供导入深链）
    for st in ("pending", "submit", "archived"):
        cur.execute(
            "INSERT INTO pending_achievements (achievement_type, achievement_data,"
            " status, submitter_type, submitter_id, file_hash, session_id)"
            " VALUES ('award', ?, ?, 'student', ?, '', 'smoke-seed-session')",
            ('{"import_session_id": "smoke-seed-session", "winner_name": "种子记录"}', st, student_id))

    # 其余业务表各 1（满足深链页渲染的数据依赖；列名对齐 full_schema NOT NULL 约束）
    cur.execute("INSERT INTO patents (patent_name, patentee) VALUES ('种子专利', '种子专利权人')")
    cur.execute("INSERT INTO software_copyrights (software_name) VALUES ('种子软著')")
    cur.execute("INSERT INTO innovation_projects (project_name) VALUES ('种子大创')")
    proj_id = cur.lastrowid
    try:
        cur.execute("INSERT INTO innovation_project_students (project_id, student_id)"
                    " VALUES (?, ?)", (proj_id, student_id))
    except Exception:
        pass  # 列名差异容错（student_id_str 形态的旧结构）
    cur.execute("INSERT INTO other_files (file_name, file_path) VALUES ('seed.txt', 'seed/seed.txt')")

    cur.execute("INSERT INTO laboratories (name) VALUES ('种子实验室')")
    lab_id = cur.lastrowid
    cur.execute("INSERT INTO laboratory_instructors (laboratory_id, teacher_id)"
                " VALUES (?, ?)", (lab_id, teacher_id))
    cur.execute("INSERT INTO laboratory_students (laboratory_id, student_id)"
                " VALUES (?, ?)", (lab_id, student_id))

    conn.commit()
    conn.close()


@pytest.fixture(scope="session")
def seeded_app(tmp_path_factory):
    """种子库上的 Flask app（DATABASE_PATH 双路径已 patch）。"""
    from app import create_app
    from config.flask import get_config
    from backend.models.app_context import reset_app_context

    db_path = tmp_path_factory.mktemp("seed_db") / "seed.db"
    _build_seeded_db(db_path)

    cfg_cls = get_config()  # Config 类（get_config() 返回类本身）
    app = create_app(cfg_cls)
    # ① Flask config 路径
    app.config["DATABASE_PATH"] = str(db_path)
    app.config["FILES_DIR"] = str(tmp_path_factory.mktemp("files"))
    # ② 配置类属性路径（auth.py 直读）；子类继承父类属性，patch 所选类即生效
    #    【必须 teardown 还原】类属性 patch 是进程级的，不还原会污染后续真库测试
    orig_db, orig_files = cfg_cls.DATABASE_PATH, cfg_cls.FILES_DIR
    cfg_cls.DATABASE_PATH = str(db_path)
    cfg_cls.FILES_DIR = app.config["FILES_DIR"]

    reset_app_context()  # 清掉此前真库测试初始化的全局上下文
    # 【关键】app.utils._core 的 _managers 缓存了首次创建的 AppContext 实例（指向真库），
    # reset_app_context 只清 backend 侧全局单例——不清这里，冒烟将静默查真实库。
    # T73 单一真源：_managers 仅存于 app.utils._core，一处复位即可
    try:
        from app.utils._core import reset_runtime_caches
        reset_runtime_caches()
    except Exception:
        pass
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SESSION_COOKIE_SECURE"] = False
    with app.app_context():
        pass  # 触发一次 app_context 就绪（不触发 manager 初始化）
    yield app
    # teardown：还原配置类属性 + 复位全局上下文 + 清 _managers 缓存
    # （下个测试按自身 config 重建；种子库 tmp 文件随 tmp_path 回收）
    cfg_cls.DATABASE_PATH = orig_db
    cfg_cls.FILES_DIR = orig_files
    reset_app_context()
    # T73 单一真源：_managers 仅存于 app.utils._core，一处复位即可
    try:
        from app.utils._core import reset_runtime_caches
        reset_runtime_caches()
    except Exception:
        pass


@pytest.fixture()
def smoke_client(seeded_app):
    """种子库 app 的 test_client（每测试独立会话）。"""
    with seeded_app.test_client() as c:
        yield c


def login_as(client, role):
    """按角色伪造登录会话（users 种子与 page_inventory 角色口径一致）。"""
    if role == "anon":
        return
    codes = {"admin": "admin", "teacher": "02110606",
             "student": "212306413", "student2": "212306999"}
    with client.session_transaction() as sess:
        sess.update({"user_id": codes[role], "role": role if role != "student2" else "student",
                     "username": codes[role], "user_name": codes[role],
                     "user_type": role if role != "student2" else "student"})
