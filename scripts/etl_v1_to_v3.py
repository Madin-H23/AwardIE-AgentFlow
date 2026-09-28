#!/usr/bin/env python
"""v3 切流 ETL:V1(SQLite `database/competitions.db`)→ MySQL(v3 `awardie_v3`)。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<v3 应用口令> python scripts/etl_v1_to_v3.py [--dry-run]

## 为什么以 V1 为源(2026-09-28 用户拍板,证据见 docs/重构二期/09-v3框架迁移/批11-迁移切流/)

V2(PG 5433)比 V1 多出的约 888 行经实测 100% 是测试数据(竞赛名全是 E2E/闭环/种子/验收,
获奖 114 条与待审 424 条全部来自测试账号 1370 陈品天)。切 V1 丢失的真实业务数据为零,
且 V1 是单个 16MB 文件、零服务依赖 —— 而 V2 依赖的 PG 实例在这台机器上反复崩溃
(后端 fork 即 `terminated by exception 0xC0000142`),切流窗口的可靠性完全不同。

`etl_v2_business_to_v3.py` 原样保留,作为 V2 路径的回退手段。

## 三个域一次跑完(顺序即依赖顺序)

1. 基础数据域   competitions / laboratories
2. 用户与角色域 system_users / awardie_user_profile / system_user_role
3. 业务成果域   15 张表

分域的原因不是"分得好看",而是 v2 路径本来就是三个独立脚本三个独立断点:
用户域有角色映射与 stock admin 顶替的特例,基础域有唯一性前置校验与自增抬升,
两者都不属于成果域。合成一个脚本后顺序即依赖顺序,少两个断点,少一次"忘了跑第二步"。

## 与 V2 路径共享的部分(不复制)

列映射 `MAPS`、补值声明 `FILL`/`NOTNULL_FALLBACK`、写入实现 `write_all`、
自校实现 `verify` —— 全部从 `etl_v2_business_to_v3.py` **import 复用**。
V1 与 V2 表名完全相同(awards/competitions/pending_achievements/…),
业务成果域的列映射本就同一份;各写一份必然漂移,而漂移的表现是
"两条路径迁出来的数据不一样、对账只在其中一条上绿"。

共享方式沿用 `v3_reconcile.py` 既有的 importlib 单例先例(它就是从
`etl_v2_business_to_v3.py` 取 `NOTNULL_FALLBACK` 的),不新造机制。

V2 脚本模块级 `import psycopg2`,而 V1 路径一行 PG 都不走。
psycopg2 缺失时装一个占位模块再加载 —— 源连接是 SQLite 文件,与 PG 无关;
让"切 V1 这条不依赖 PG 服务的路"因为一个用不到的驱动而跑不起来是本末倒置。

## SQLite 与 PG 的类型差异(逐条实测,不是推测)

| 语义 | PG(v2 源) | SQLite(V1 源) | 本脚本的处理 |
|---|---|---|---|
| jsonb | psycopg2 自动解析成 dict/list | TEXT 字符串 | `s_*` 原样透传;`d_*` 先 loads |
| boolean | 真 boolean | INTEGER 0/1 | 实测全库 10 个布尔列 typeof 均为 integer,取值只有 0/1 |
| timestamp | 带时区 datetime | `'2026-01-31 13:20:26'` 无时区字符串 | 原样透传,**不取 NOW()、不做时区换算** |
| real/numeric | Decimal/float | float | 无需转换 |
| BLOB | BYTEA | bytes | 仅 `templates.sample_image_blob` 有 20 处 |

时间列实测:V1 全部 22 个时间列的非空值 **100% 符合 `YYYY-MM-DD HH:MM:SS`**,
零例外。V1 本来就存本地朴素时间,换算时区反而是引入偏移。

## V1 比 V2 少的两列(源表根本没有,不是映射写错)

- `awards.certificate_path` —— 文件域批2 才加的列,V1 早于它
- `templates.sample_image_path` —— 同上

两列在 v3 侧都可空,故补 NULL 并**在 [missing] 段显式上报**。
不静默:「源表没这列」和「源表有这列但值是 NULL」是两回事,后者是数据,前者是历史。

## 模板样本图:V1 的 BLOB 里还活着(handoff 结论的修正)

handoff 记的是「V1 的文件主体已不在磁盘上」,那是就 `files/` 各目录说的。
但 V1 把 20 张模板样本图以 **BLOB 存在数据库里**(`templates.sample_image_blob`),
实测与 v3 现库 `sample_image_path` 指向的 20 个磁盘文件 **sha256 全部相同、id 集合相同**。

所以「接受历史证书图不显示」这条决定**不适用于模板样本图** —— 它们没丢。
本脚本按 `migrate_template_image_blobs.py` 同一套内容寻址约定
(sha256 前 16 位 + 魔数判型扩展名)还原 `sample_image_path`,文件名与现库逐条相同
(实测 20/20 命中同名的磁盘文件),即切流对这 20 张图是零回归。

⚠️ 已知遗留缺陷(本脚本**如实还原**而非掩盖,留给后续票):
现库存的是 `files\\v2\\<sha16>.jpg` —— v2 迁移脚本用 `str(Path(...))` 拼的,
在 Windows 上落成反斜杠;而 v3 自己的 `AwardieFileStorage.store()` 结尾有
`.replace('\\', '/')`,即 v3 的规范形式是**正斜杠**。本脚本写正斜杠,与 v3 约定一致。
但更要紧的是前缀:现库存的是「相对 CWD 全路径」,而 v3 的
`AwardieFileStorage.resolve()` 按 `awardie.file.root`(默认 `files/v3`)解析,
两者对不上 —— 即这 20 条引用**在现库就已经是悬空的**(v3 也还没有展示样本图的端点)。
要真正修好,应把字节搬进 v3 存储根并改存 `root.relativize()` 的结果,
那是独立的一张票,不在切流范围内。
"""
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import types
from collections import Counter
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = os.environ.get('AWARDIE_V1_DB', str(ROOT / 'database' / 'competitions.db'))
MYSQL = dict(host='127.0.0.1', port=3307, db=os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3'),
             user=os.environ.get('AWARDIE_MYSQL_USER', 'awardie_v3'),
             password=os.environ.get('AWARDIE_MYSQL_PASSWORD', ''), charset='utf8mb4')

ROLE_MAP = {'admin': 100, 'teacher': 101, 'student': 102}
# v2 admin 追加 super_admin(芋道系统菜单挂超管角色;纯 awardie_admin 只有业务菜单,管不了用户/角色)
EXTRA_ROLES = {100: [1]}
# 芋道 stock admin(id=1, username=admin)会被 V1 的 users.id=1 顶替。
# V1 的 admin 其实在 id=1832(V1 的 id=1 是学生 212206095),顶替 id=1 的意义在于
# **保证全库只有一行 username='admin'** —— selectByUsername 命中两行会 TooManyResults。
STOCK_ADMIN = (1, 'admin')
ALNUM = re.compile(r'^[A-Za-z0-9]+$')

COMPETITION_COLS = [
    'id', 'competition_name', 'official_website', 'organizer', 'competition_time',
    'participant_requirements', 'grade_category', 'brief_description', 'alias_list',
    'white_list', 'watch_list', 'is_auto_added', 'creator', 'updater', 'tenant_id',
]
COMPETITION_BOOL = ('white_list', 'watch_list', 'is_auto_added')
LAB_COLS = ['id', 'name', 'description', 'creator', 'updater', 'tenant_id']
# V1 与 v2 的 users 列完全同名(见文件头「与 V2 路径共享」),故查询语句一致
USER_SRC_COLS = ('id', 'login_code', 'name', 'role', 'password_hash', 'user_activated', 'phone',
                 'major', 'grade', 'title', 'qq', 'skills', 'profile_is_public')


def load_v2_defs():
    """加载 V2 路径的列映射与写入/自校实现(单一事实来源,见文件头)。"""
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        # V1 路径不连 PG,占位即可;真要用到会在属性解析处炸,而不会静默走错源
        sys.modules['psycopg2'] = types.ModuleType('psycopg2')
    spec = importlib.util.spec_from_file_location(
        'etl_v2_biz', str(Path(__file__).resolve().parent / 'etl_v2_business_to_v3.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V2 = load_v2_defs()

# 模板样本图:与 scripts/migrate_template_image_blobs.py 同一套约定(内容寻址 + 魔数判型)。
# 按 (魔数前缀, 扩展名) 列表顺序匹配而非字典 —— JPEG 的魔数只有 3 字节(FF D8 FF),
# 第 4 字节是 APP0/EXIF 标记位(实测 V1 全部 20 张都是 FF D8 FF E0),按 4 字节取键会一张都认不出。
BLOB_MAGIC = [(b'\xff\xd8\xff', 'jpg'), (b'\x89PNG', 'png'), (b'%PDF', 'pdf')]

# 运行期报告(全部显式打印,不静默)
MISSING_SRC_COLS: dict[str, list[str]] = {}   # 源表根本没有的映射列
JSON_PARSE_FAIL: Counter = Counter()          # 解析不了的 JSON → 目标 JSON 列会变 NULL
ABSENT_REPORT: list[str] = []                 # 列在、但值为 NULL 导致的已知缺口
BLOB_DERIVED = 0                              # 由 BLOB 还原出 sample_image_path 的行数


# ---------------- SQLite 转换器 ----------------
def s_tm(v):
    """V1 时间戳是无时区字符串,原样交给 MySQL 解析。

    **不取 NOW()、不换算时区**:V1 存的就是本地朴素时间,换算只会凭空引入偏移。
    保留成函数而不是直接写 None 转换器,是为了让 MAPS 里的 't' 在两条路径上
    指向同一处、差异集中在这里一行注释里。
    """
    return v


def s_bl(v):
    """V1 的 boolean 是 INTEGER 0/1(SQLite 无真 boolean 类型)。

    实测全库 10 个布尔列 typeof 均为 integer、取值只有 0/1,故直接归一为 int。
    写成 `1 if v else 0` 而不是 `int(bool(v))`:空串在 Python 里是 falsy,
    而它若真出现在数据里,归一成 0 就是把「无法识别」说成了「否」。
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return 1 if v else 0
    if isinstance(v, str) and v.strip() in ('0', '1'):
        return int(v.strip())
    raise SystemExit(f'[FATAL] 布尔列出现非 0/1 值 {v!r}(type={type(v).__name__})——'
                     f'源侧语义与 V1 不符,中止而不是猜')


def s_js(v):
    """JSON 列 → 字符串(v3 的 RespVO 是 String,前端自行 parse)。V1 存的就是字符串。"""
    return v


def s_jd(v, where='?'):
    """JSON 字符串 → dict/list(MySQL JSON 列用)。

    解析不了**不能默默变 NULL** —— 那等于把一段内容从库里抹掉且不留痕迹。
    计入 JSON_PARSE_FAIL 并原样回退成字符串,由写库时报错暴露(目标列是 JSON,
    塞非 JSON 会被 MySQL 拒绝,是响亮的失败而不是静默的数据损失)。
    """
    if v is None or isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        JSON_PARSE_FAIL[where] += 1
        return v


def coerce_sentinel(target, col, v):
    """数字列里的角色名哨兵 → NULL(口径与 v2 的 PG 强类型一致,见 SENTINEL_TO_NULL)。"""
    if isinstance(v, str) and v == SENTINEL_TO_NULL[(target, col)]:
        SENTINEL_HITS[f'{target}.{col}'] += 1
        return None
    return v


CONV = {'t': s_tm, 'b': s_bl, 's': s_js}

# SQLite 弱类型 → PG 强类型,方向是反的:V1 允许在数字列里塞字符串,PG 塞不进去。
# 全库数字列普查(目标 int/bigint × 源 typeof)确认**只有两处**,其余 46 个数字列 100% 是 integer:
#   review_logs.reviewer_id            435 行 'admin'
#   achievement_audit_log.operator_id    3 行 'admin'(过 AUDIT_FILTER 后剩 2 行)
# 归一口径 = **置 NULL,与 v2 一致**,不另发明映射:PG 侧是 bigint 写不进字符串,
# v2 应用落的就是 NULL,现库可查证(awardie_review_logs 435 行 reviewer_id=NULL;
# awardie_achievement_audit_log id=9/1694 operator_id=NULL)。
# 身份没丢 —— 靠 reviewer_type='admin' 与 operator_code='admin' 承载,
# 数字列本来就只该放用户主键,'admin' 是角色名不是 id。
SENTINEL_TO_NULL = {
    ('awardie_review_logs', 'reviewer_id'): 'admin',
    ('awardie_achievement_audit_log', 'operator_id'): 'admin',
}
SENTINEL_HITS: Counter = Counter()


def s_jd_bound(where):
    return lambda v: s_jd(v, where)


# ---------------- 源读取 ----------------
def open_src():
    """以**只读**方式打开 V1。

    切流的源库是生产数据,ETL 对它只发 SELECT。`mode=ro` 让「写错了」在语句层就失败,
    而不是靠"我记得别写" —— 后者靠不住,而这里改错了也没有备份可以回退。
    """
    if not os.path.isfile(SRC_DB):
        raise SystemExit(f'[FATAL] 找不到 V1 源库 {SRC_DB}')
    con = sqlite3.connect(f'file:{SRC_DB}?mode=ro', uri=True)
    con.execute('PRAGMA query_only = ON')
    return con


def columns_of(cur, table):
    return {r[1] for r in cur.execute(f'PRAGMA table_info({table})')}


def fetch_business(cur):
    """读 15 张业务表,产出 V2 路径 write_all/verify 认的数据结构。

    `{target: (cols, raw, rows)}`:cols 目标列名、raw 源行(按 cols 对齐补齐)、
    rows 待写值元组。raw 必须与 cols 同序 —— verify 靠 raw[i][0] 取 id。
    """
    data = {}
    for target in V2.ORDER:
        spec = V2.MAPS[target]
        src = V2.SOURCES[target]
        have = columns_of(cur, src)
        need = [p for p, _, _ in spec]
        absent = [c for c in need if c not in have]
        if absent:
            MISSING_SRC_COLS[target] = absent
            # 源表没有的列不 SELECT,值恒为 None(见文件头「V1 比 V2 少的两列」)
        present = [c for c in need if c in have]

        sql = f"SELECT {', '.join(present)} FROM {src}"
        if target == 'awardie_achievement_audit_log':
            sql += V2.AUDIT_FILTER
        sql += f" ORDER BY {present[0]}"
        raw_rows = cur.execute(sql).fetchall()

        cols = [v3 for _, v3, _ in spec]
        fill = V2.FILL.get(target, {})
        if fill:
            cols = cols + list(fill.keys())
        fb = V2.NOTNULL_FALLBACK.get(target, {})

        raw_out, rows = [], []
        for r in raw_rows:
            if len(r) != len(present):
                raise SystemExit(f'[FATAL] {src} 返回 {len(r)} 列,期望 {len(present)} —— 中止')
            it = iter(r)
            # 源没有的列置 None,位置对齐:cols 与 raw 必须同序,否则 verify 取到的 id 是别的列
            vals = [next(it) if c in have else None for c in need]
            raw_out.append(tuple(vals))
            out = []
            for i, (_p, v3, conv) in enumerate(spec):
                v = vals[i]
                if (target, v3) in SENTINEL_TO_NULL:
                    v = coerce_sentinel(target, v3, v)
                if conv == 'd':
                    out.append(s_jd_bound(f'{target}.{v3}')(v))
                else:
                    out.append(CONV[conv](v) if conv else v)
            if fill:
                out = out + [fill[c] for c in fill]
            for col, fallback in fb.items():
                if col in cols and out[cols.index(col)] is None:
                    out[cols.index(col)] = fallback
            rows.append((out, None))
        data[target] = (cols, raw_out, rows)
    return data


# ---------------- 基础数据域 ----------------
def read_base(cur):
    comps = cur.execute(
        f"SELECT {', '.join(c for c in COMPETITION_COLS if c not in ('creator', 'updater', 'tenant_id'))} "
        'FROM competitions ORDER BY id').fetchall()
    labs = cur.execute('SELECT id, name, description FROM laboratories ORDER BY id').fetchall()
    return comps, labs


def validate_base(cur, comps, labs):
    """前置校验:唯一性。ETL 依赖「竞赛名唯一」这一语义,重了会静默合并两条成果。"""
    ok = True
    for label, rows, idx in (('竞赛', comps, 1), ('实验室', labs, 1)):
        names = [r[idx] for r in rows]
        dup = sorted({n for n, k in Counter(names).items() if k > 1})
        if dup:
            print(f'[FATAL] V1 {label}名重复 {len(dup)} 个: {dup[:5]} —— 中止')
            ok = False
    # id 异位冲突:目标库同 id 不同名,说明两条源不是同一份历史,静默覆盖就是改数据
    return ok


def _upsert_sql(table, cols):
    return (f"INSERT INTO `{table}` ({', '.join('`' + c + '`' for c in cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) ON DUPLICATE KEY UPDATE "
            + ', '.join(f"`{c}` = VALUES(`{c}`)" for c in cols if c != 'id'))


def write_base(conn, cur, comps, labs):
    comp_payload = []
    for row in comps:
        vals = list(row)
        for i, col in enumerate(COMPETITION_COLS):
            if col in COMPETITION_BOOL:
                vals[i] = s_bl(vals[i])
        comp_payload.append(tuple(vals + ['etl', 'etl', 1]))
    if comp_payload:
        cur.executemany(_upsert_sql('awardie_competitions', COMPETITION_COLS), comp_payload)
    lab_payload = [tuple(list(row) + ['etl', 'etl', 1]) for row in labs]
    if lab_payload:
        cur.executemany(_upsert_sql('awardie_laboratories', LAB_COLS), lab_payload)
    conn.commit()


# ---------------- 用户与角色域 ----------------
def read_users(cur):
    return cur.execute(f"SELECT {', '.join(USER_SRC_COLS)} FROM users ORDER BY id").fetchall()


def write_users(conn, cur, rows):
    """与 v2 路径同一套语义:角色映射、stock admin 顶替、资料扩展、抬自增。"""
    user_sql = """
        INSERT INTO system_users (id, username, password, nickname, status, mobile,
                                  creator, updater, tenant_id, dept_id, post_ids, remark)
        VALUES (%s, %s, %s, %s, %s, %s, 'etl', 'etl', 1, 1, '[]', %s)
        ON DUPLICATE KEY UPDATE
            username = VALUES(username), password = VALUES(password), nickname = VALUES(nickname),
            status = VALUES(status), mobile = VALUES(mobile), updater = 'etl'
    """
    profile_sql = """
        INSERT INTO awardie_user_profile (user_id, major, grade, title, qq, skills, profile_is_public, creator, updater)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'etl', 'etl')
        ON DUPLICATE KEY UPDATE
            major = VALUES(major), grade = VALUES(grade), title = VALUES(title),
            qq = VALUES(qq), skills = VALUES(skills), profile_is_public = VALUES(profile_is_public),
            updater = 'etl'
    """
    cur.execute("SELECT id, username FROM system_users")
    existing = dict(cur.fetchall())
    clash = [(r[0], r[1], existing[r[0]]) for r in rows
             if r[0] in existing and existing[r[0]] != r[1]
             and (r[0], existing[r[0]]) != STOCK_ADMIN]
    if clash:
        raise SystemExit(f'[FATAL] 目标库同 id 异 username 冲突(需人工裁决): {clash[:5]}')

    ids = []
    for r in rows:
        uid, code, name, role, pw, activated, phone, major, grade, title, qq, skills, pub = r
        cur.execute(user_sql, (uid, code, pw or '', name, 0 if activated else 1,
                               phone or None, f'v1 迁移({role})'))
        cur.execute("DELETE FROM system_user_role WHERE user_id = %s", (uid,))
        for rid in [ROLE_MAP[role]] + EXTRA_ROLES.get(ROLE_MAP[role], []):
            cur.execute("INSERT INTO system_user_role (role_id, user_id, creator, updater, tenant_id) "
                        "VALUES (%s, %s, 'etl', 'etl', 1)", (rid, uid))
        cur.execute(profile_sql, (uid, major, grade, title, qq, skills, 1 if pub else 0))
        ids.append(uid)
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM system_users")
    nxt = cur.fetchone()[0]
    cur.execute(f"ALTER TABLE system_users AUTO_INCREMENT = {nxt}")
    conn.commit()
    return ids, nxt


# ---------------- 模板样本图 ----------------
def template_sample_paths(cur):
    """V1 的 templates.sample_image_blob → sample_image_path(内容寻址,与现库同值)。

    V1 早于文件域,没有 sample_image_path 列,但 20 张样本图以 BLOB 活着。
    不还原就是白丢 20 张图;按内容寻址还原出的文件名与现库指向的磁盘文件逐条同名,
    即切流对这 20 张图零回归(前缀与分隔符按 v3 存储服务自己的规范,见文件头)。
    """
    global BLOB_DERIVED
    out = {}
    for tid, blob in cur.execute(
            "SELECT id, sample_image_blob FROM templates "
            'WHERE sample_image_blob IS NOT NULL ORDER BY id'):
        data = bytes(blob)
        ext = next((e for magic, e in BLOB_MAGIC if data.startswith(magic)), None)
        if ext is None:
            ABSENT_REPORT.append(f'templates.id={tid} 样本图魔数不在白名单(头4字节={data[:4].hex()}),已跳过')
            continue
        out[tid] = f'files/v2/{hashlib.sha256(data).hexdigest()[:16]}.{ext}'
        BLOB_DERIVED += 1
    return out


def main() -> int:
    global BLOB_DERIVED
    dry = '--dry-run' in sys.argv
    if not MYSQL['password']:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    src = open_src()
    cur = src.cursor()
    comps, labs = read_base(cur)
    users = read_users(cur)
    if not validate_base(cur, comps, labs):
        return 1
    tpl_paths = template_sample_paths(cur)
    data = fetch_business(cur)

    # 模板样本图写回 business 数据(awardie_templates 已在 data 里)
    cols, raw, rows = data['awardie_templates']
    if tpl_paths:
        idx = cols.index('sample_image_path')
        new_rows = []
        for (vals, _s), r in zip(rows, raw):
            vals = list(vals)
            tid = r[0]
            if tid in tpl_paths:
                vals[idx] = tpl_paths[tid]
            new_rows.append((vals, None))
        data['awardie_templates'] = (cols, raw, new_rows)

    total = sum(len(v[2]) for v in data.values())
    print(f'[read] V1 源库 {SRC_DB}')
    print(f'[read] 业务成果域 {total} 行 / {len(data)} 张表;基础域 competitions={len(comps)} '
          f'laboratories={len(labs)};用户 {len(users)}')
    for t in V2.ORDER:
        print(f'   {t:<40} {len(data[t][2]):>5}')

    print()
    for t, cols_ in MISSING_SRC_COLS.items():
        print(f'[missing] {t}: 源表无 {", ".join(cols_)} 列(V1 早于该列的引入),按 NULL 迁;'
              f'目标列可空,不丢数据')
    for t, n in V2.FILL.items():
        print(f'[fill] {t}: granted_role 源侧无此列,按声明值 '
              f'{V2.FILL[t].get("granted_role")} 补 {len(data[t][2])} 行')
    if BLOB_DERIVED:
        print(f'[blob] templates: 由 V1 sample_image_blob 还原 sample_image_path {BLOB_DERIVED} 行'
              f'(内容寻址,与现库同值;V1 的样本图没丢,不受"证书图不显示"影响)')
    for w in ABSENT_REPORT:
        print(f'[warn] {w}')
    for where, n in JSON_PARSE_FAIL.items():
        print(f'[warn] {where}: {n} 行不是合法 JSON,原样透传(MySQL JSON 列会拒收并中断,属响亮失败)')
    for where, n in SENTINEL_HITS.items():
        print(f'[sentinel] {where}: {n} 行源侧是角色名哨兵而非用户 id,按 v2 口径置 NULL;'
              f'身份由 reviewer_type/operator_code 承载,非丢数')

    users_dup = [c for c, k in Counter(r[1] for r in users).items() if k > 1]
    if users_dup:
        print(f'[FATAL] V1 login_code 重复 {users_dup[:5]},中止')
        return 3
    bad_role = sorted({r[3] for r in users} - set(ROLE_MAP))
    if bad_role:
        print(f'[FATAL] V1 存在未映射角色 {bad_role},中止')
        return 4
    non_alnum = [r[0] for r in users if not (r[1] and ALNUM.match(r[1]))]
    if non_alnum:
        print(f'[check] 非字母数字 login_code(芋道登录校验不通过,照迁但上报): {non_alnum}')

    if dry:
        print('[dry-run] 未落盘')
        return 0

    conn = pymysql.connect(**MYSQL)
    myc = conn.cursor()
    write_base(conn, myc, comps, labs)
    ids, nxt = write_users(conn, myc, users)
    print(f'[write] competitions={len(comps)} laboratories={len(labs)} users={len(ids)} '
          f'AUTO_INCREMENT->{nxt}')

    V2.write_all(data, conn)
    problems = V2.verify(data, myc)

    myc.execute("SELECT COUNT(*) FROM system_users")
    n_sys = myc.fetchone()[0]
    myc.execute("SELECT COUNT(*) FROM awardie_user_profile")
    n_prof = myc.fetchone()[0]
    print(f'[verify] system_users={n_sys} (源 {len(users)}) awardie_user_profile={n_prof}')
    if n_sys < len(users) or n_prof < len(users):
        problems += 1
        print('[verify] [异常] 用户域行数少于源')
    for table in ('awardie_competitions', 'awardie_laboratories'):
        myc.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}")
        val = myc.fetchone()[0]
        myc.execute(f"ALTER TABLE {table} AUTO_INCREMENT = {val}")
    conn.commit()
    conn.close()
    if problems:
        print(f'[FAIL] {problems} 处对账异常')
        return 1
    print('[ok] V1 切流 ETL 完成且对账齐平')
    return 0


if __name__ == '__main__':
    sys.exit(main())
