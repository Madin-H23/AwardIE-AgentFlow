#!/usr/bin/env python
"""v3 切流对账:源库与目标库(v3 MySQL)逐表逐行核验。

与 ETL 的自校不同——自校只验「源 id 都在目标里」,抓不到「id 都在但字段写错」。
本工具做三层:
  L1 行数:目标行数 vs 源行数(允许 dev 库多出测试行,只报差额不判失败)
  L2 id 集合:双向差集。**源有目标无 = 真实丢数,直接 FAIL**
  L3 内容哈希:对每张表选若干关键字段,按 id 排序算 sha256,两边比对。
     抓的是「行在、值不对」——列映射写反、JSON 序列化错、时区偏移都会在这里现形。

## 源库:默认 V1(SQLite),`--source v2` 可切回 PG(2026-09-28 用户拍板)

V1 与 V2 **表名完全相同**,故 CHECKS 里的源表名两条路径通用,一个都不用改。
V1 的 `achievement_audit_log` 与 V2 同源(实测 is_test 分布 1674/16/3 完全一致,
列结构也一致),故 AUDIT_FILTER 两条路径同样通用。

保留 `--source v2` 不是为了日常使用,而是**回退手段**:切流若在 V1 上出问题,
还能退回 V2 方案重跑,而不必先把对账工具也改回去(对账工具改错 = 闸门失灵,
是最不能出错的那个)。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/v3_reconcile.py [--verbose] [--full] [--cover]
    ... python scripts/v3_reconcile.py --source v2      # 回退到 PG 源

退出码:0 = 对账齐平;1 = 有丢数或内容不一致(切流闸门不能过)。
"""
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

import pymysql

# 从 ETL 脚本里取 NOTNULL_FALLBACK —— 「已声明的例外」只写一处,两个工具都认它。
# 不各写一份:各写一份迟早漂移,漂移的表现是对账误报或漏报,都伤闸门的可信度。
# 取的是 V1 那份:V1 与 V2 共用同一份 MAPS/补值声明(见 etl_v1_to_v3.py 文件头),
# 切 V1 后它才是对账真正要认的转换。
_spec = importlib.util.spec_from_file_location('etl_v1', str(Path(__file__).resolve().parent / 'etl_v1_to_v3.py'))
_etl = importlib.util.module_from_spec(_spec)
sys.modules['etl_v1'] = _etl  # etl_v1 内部再 importlib 加载 V2 模块,注册可避免重复实例化
_spec.loader.exec_module(_etl)
NOTNULL_FALLBACK = _etl.V2.NOTNULL_FALLBACK
FILL_REPORT: dict[str, int] = {}
SENTINEL_REPORT: dict[str, int] = {}

SOURCE = 'v2' if '--source v2' in sys.argv else 'v1'
ROOT = Path(__file__).resolve().parent.parent
V1_DB = os.environ.get('AWARDIE_V1_DB', str(ROOT / 'database' / 'competitions.db'))

# 目标列名 → 源列名(取自共享 MAPS 的反查),用于 --full 验 create_time/update_time:
# 目标叫 create_time、源叫 created_at,名字对不上不等于没法验。
# 只收**全局无歧义**的映射:同一个 v3 列名在 MAPS 里对应到多个不同源列名时丢弃,
# 否则会拿 A 表的源列名去查 B 表。歧义宁可漏验也不猜。
_by_v3: dict[str, set] = {}
for _tgt, _spec in _etl.V2.MAPS.items():
    for _p, _v3, _cv in _spec:
        _by_v3.setdefault(_v3, set()).add(_p)
V3_TO_SRC = {v3: next(iter(ps)) for v3, ps in _by_v3.items() if len(ps) == 1}

PG = dict(host='127.0.0.1', port=5433, dbname='awardie_dev', user='postgres',
          password=os.environ.get('PGPASSWORD', 'postgres'))
MYSQL = dict(host='127.0.0.1', port=3307, db=os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3'),
             user=os.environ.get('AWARDIE_MYSQL_USER', 'root'),
             password=os.environ.get('AWARDIE_MYSQL_PASSWORD', ''), charset='utf8mb4')

# 表 → (v2源表, 哈希用的关键字段, id 表达式)
# 关键字段选「业务语义最重、且映射最容易写错」的那几列,不是全字段——
# 全字段哈希会因框架列(creator/update_time)和 JSON 键序差异产生假失败。
CHECKS = [
    # 更早批次迁的域:切流同样依赖它们,不能只对账批11 的成果域
    ('awardie_competitions', 'competitions', 'id',
     ['competition_name', 'organizer', 'white_list', 'watch_list', 'is_auto_added']),
    ('awardie_laboratories', 'laboratories', 'id', ['name', 'description']),
    # awardie_awards 把「批11 整批存在的理由」那几列全纳入哈希:
    # llm_prompt/llm_response/validation_result 是批11 补的 4 列里的 3 个,
    # image_hash/certificate_path/ocr_result/extract_json 是 OCR 与物化链的命脉。
    # 它们若映射写反或 jsonb 序列化错,首版的抽样哈希一条都验不到。
    ('awardie_awards', 'awards', 'id',
     ['competition_name_in_file', 'winner_name', 'award_level', 'competition_level', 'year',
      'granted_role', 'image_hash', 'certificate_id', 'certificate_path', 'supervisor_name',
      'ocr_result', 'extract_json', 'llm_prompt', 'llm_response', 'validation_result',
      'submitter_type', 'submitter_id', 'competition_id', 'date', 'track', 'issuer']),
    ('awardie_pending_achievements', 'pending_achievements', 'id',
     ['achievement_type', 'status', 'submitter_type', 'review_comment',
      'achievement_data', 'validation_result', 'file_hash', 'file_path', 'reviewer_id',
      'assigned_reviewer_type', 'reviewer_type', 'ocr_text', 'llm_prompt', 'llm_response']),
    ('awardie_innovation_projects', 'innovation_projects', 'id',
     ['project_no', 'project_name', 'project_type', 'status', 'start_date', 'end_date',
      'funding_amount', 'student_leader_name', 'student_leader_id', 'other_members',
      'supervisors', 'laboratory_id']),
    ('awardie_software_copyrights', 'software_copyrights', 'id', ['software_name', 'registration_number']),
    ('awardie_other_files', 'other_files', 'id', ['file_name', 'file_type']),
    ('awardie_templates', 'templates', 'id', ['template_type', 'competition_id', 'language']),
    ('awardie_laboratory_downloads', 'laboratory_downloads', 'id', ['file_name', 'laboratory_id']),
    ('awardie_laboratory_images', 'laboratory_images', 'id', ['image_path', 'laboratory_id']),
    ('awardie_review_logs', 'review_logs', 'id', ['pending_id', 'action_type', 'achievement_type']),
    ('awardie_achievement_audit_log', 'achievement_audit_log', 'id',
     ['achievement_id', 'achievement_kind', 'action_type', 'action_result']),
    # 关联表无 id,用 (外键, 内键) 复合哈希
    ('awardie_award_student_winners', 'award_student_winners', None, ['award_id', 'student_id']),
    ('awardie_award_teacher_winners', 'award_teacher_winners', None, ['award_id', 'teacher_id']),
    ('awardie_award_related_students', 'award_related_students', None, ['award_id', 'student_id']),
    ('awardie_innovation_project_students', 'innovation_project_students', None,
     ['project_id', 'student_id', 'role']),
]
# --full:把 L3 从「抽样关键列」扩到「全部迁移列」。切流前跑一次。
# 抽样是为避免 JSON 键序/框架列造成假失败,但抽样就意味着没验的列是隐形的——
# 覆盖率自查会把它们列出来,--full 则真的全验。
VERBOSE_COVERAGE = '--full' in sys.argv or '--cover' in sys.argv
FULL = '--full' in sys.argv

if FULL:
    # 把每张表的 L3 取样列扩到**全部迁移列**。
    # 此前 `--full` 只打开了覆盖率打印、并没有真的扩列 —— 也就是说「跑 --full 就全验了」
    # 这句承诺从来没兑现过,而切流正好是最需要它的那一次:L3 抽样只覆盖 42% 的迁移列,
    # 剩下 58% 写错了四层判据会全绿。未覆盖的恰是批11 整批存在的理由
    # (llm_prompt/llm_response/validation_result 之外的多数业务列)。
    # 排序固定:新增列**追加在原列表之后**,不打乱原有次序。
    # 关联表(idcol is None)靠 (sel[0], sel[1]) 当主键,一旦重排就变成
    # (award_id, create_time) 这种组合,于是「缺迁」报出一堆
    # (998, '2026-08-17 02:09:24') 这样的假键 —— 闸门误报比不报更坏。
    #
    # **必须排除 idcol 本身**:fetch_src/fetch_my 都把 id 提到 SELECT 首位,
    # 而下面归一化用的下标是按 cols 枚举的、并对非首位列 +1 修正。
    # 一旦 id 混进 cols,fetch 又把它从原位摘走提到最前,cols 与实际行就错开一位,
    # 归一化会打到隔壁列上 —— 症状是「哨兵计数 551(其实是 reviewer_type 的行数)
    # 而 reviewer_id 原封不动」,哈希仍然不一致,且极难一眼看出。
    # id 列本来也不必进内容哈希:L2 已经在比 id 集合了。
    CHECKS = [
        (t, s, i, c + [x for x in sorted({v3 for _p, v3, _cv in _etl.V2.MAPS.get(t, [])})
                       if x not in c and x != i])
        for t, s, i, c in CHECKS
    ]

# audit_log 只迁非测试行,对账口径必须一致
AUDIT_FILTER = ' WHERE is_test = false AND is_redundant = false'


def norm(v):
    """跨库可比的规范化:None/空串统一、时间截断到秒、JSON 归一、数字字符串化。"""
    if v is None:
        return ''
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        # ⚠️ 不能用 if v —— b'\x00' 长度 1 是 truthy,会把 0 和 1 都算成 '1',
        # 导致 BIT(1) 列在闸门口报假警。按字节真值取。
        return '1' if int.from_bytes(bytes(v), 'big') != 0 else '0'
    # JSON 列必须归一后再比,否则报的是假警:
    #   源侧 PG 会把 jsonb 自动解析成 Python 对象(dict/True/None/单引号);
    #   V1 侧是 SQLite 的 TEXT 字符串,键序取决于当初谁写的;
    #   目标侧 MySQL TEXT/JSON 列存的是规范 JSON(true/null/双引号)——
    #   语义完全相同,但**键序也未必相同**,直接比字符串必然不等。
    #   两边都按 sort_keys 重新序列化,比的就只剩内容本身。
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
    s = str(v)
    if s[:1] in ('{', '['):
        try:
            return json.dumps(json.loads(s), sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            pass
    # 2026-01-20 11:43:32+08:00 → 2026-01-20 11:43:32(去掉时区,两边都已是同一本地时刻)
    if len(s) >= 25 and (s[19] == '+' or s[19] == '-'):
        s = s[:19]
    if 'T' in s and len(s) >= 19:
        s = s[:19].replace('T', ' ')
    if len(s) == 19 and s[10] == ' ':
        s = s[:19]
    return s


def open_source():
    """按 --source 选源。V1 只读打开 —— 对账对源库只发 SELECT,不该有能力改它。"""
    if SOURCE == 'v2':
        try:
            import psycopg2
        except ImportError:
            raise SystemExit('--source v2 需要 psycopg2;默认源已是 V1,直接不带该参数即可')
        con = psycopg2.connect(**PG)
        con.cursor().execute('SELECT 1')
        return con, f"v2 PG {PG['host']}:{PG['port']}/{PG['dbname']}"
    if not os.path.isfile(V1_DB):
        raise SystemExit(f'[FATAL] 找不到 V1 源库 {V1_DB}')
    con = sqlite3.connect(f'file:{V1_DB}?mode=ro', uri=True)
    con.execute('PRAGMA query_only = ON')
    return con, f'v1 SQLite {V1_DB}'


def fetch_src(cur, src, cols, idcol, filter_=''):
    """读源侧。PG 与 SQLite 的 SQL 文本在无占位符时完全一致,故同一段代码通吃。

    切到 V1 后必须处理两件事,都不是「改个名字」那么简单:
    1. `CHECKS` 里 awardie_awards 含 `certificate_path`,而 V1 的 awards 表**根本没有这一列**
       (V1 早于文件域)。不去掉就是 `no such column` 崩在对账第一张表上;
       静默去掉又会让「这一列没验过」看不见。故去掉并交由调用方显式上报。
    2. 目标列 `create_time`/`update_time` 在源侧叫 `created_at`/`updated_at`。
       这两列恰恰是批11 审查最在意的(时间线被 NOW() 覆盖 = 历史全变成今天),
       所以按共享 MAPS 反查回源列名去验,而不是因为「名字对不上」就不验。
    """
    have = {r[1] for r in cur.execute(f'PRAGMA table_info({src})')} \
        if SOURCE == 'v1' else set(cols)
    pairs, absent = [], []          # (v3列名, 源列名)
    for c in cols:
        if c in have:
            pairs.append((c, c))
            continue
        src_col = V3_TO_SRC.get(c)
        if src_col and src_col in have:
            pairs.append((c, src_col))       # 目标列在源侧换了名(created_at → create_time)
        else:
            absent.append(c)
    if not pairs:
        return [], absent
    if idcol is not None:
        # idcol 单独提到首位(与 fetch_my 同序,否则两边哈希是错位相比)
        pairs = [(idcol, idcol)] + [p for p in pairs if p[0] != idcol]
    sel = [s for _c, s in pairs]
    sql = f"SELECT {', '.join(sel)} FROM {src}{filter_} ORDER BY {sel[0]}"
    if idcol is None and len(sel) > 1:
        sql += f", {sel[1]}"
    cur.execute(sql)
    return cur.fetchall(), absent


def fetch_my(cur, target, cols, idcol):
    sel = cols if idcol is None else [idcol] + [c for c in cols if c != idcol]
    sql = f"SELECT {', '.join('`'+c+'`' for c in sel)} FROM `{target}` ORDER BY {sel[0]}"
    if idcol is None and len(sel) > 1:
        sql += f", `{sel[1]}`"
    cur.execute(sql)
    return cur.fetchall()


def main() -> int:
    verbose = '--verbose' in sys.argv
    if not MYSQL['password']:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2
    src_con, src_label = open_source()
    src_cur = src_con.cursor()
    my = pymysql.connect(**MYSQL)
    myc = my.cursor()

    failed, warned, uncovered = [], [], []
    print(f'源库: {src_label}')
    print(f"{'表':<40} {'源':>6} {'目标':>6} {'缺迁':>6}  内容哈希")
    print('-' * 92)
    for target, src, idcol, cols in CHECKS:
        filt = AUDIT_FILTER if target == 'awardie_achievement_audit_log' else ''
        src_rows, absent = fetch_src(src_cur, src, cols, idcol, filt)
        used = [c for c in cols if c not in absent]
        if absent:
            uncovered.append((target, absent))
        my_rows = fetch_my(myc, target, used, idcol)

        def keyset(rows, idcol):
            if idcol is not None:
                return {r[0] for r in rows}
            return {(r[0], r[1]) for r in rows}

        # 已声明的转换:源侧 NULL 会被 ETL 填成 NOTNULL_FALLBACK 的值;
        # 源侧的数字列哨兵('admin' 之类角色名)会被 ETL 归一成 NULL。
        # 在算哈希前对源侧做同样的归一,否则这些行会被报成「内容不一致」——
        # 那不是数据问题,是已知且有意的转换。计数后单独上报,不藏。
        fb = NOTNULL_FALLBACK.get(target, {})
        sentinel = {c: s for (t_, c), s in _etl.SENTINEL_TO_NULL.items() if t_ == target}
        normalized = 0
        sentinel_hits = 0
        if fb or sentinel:
            idx = {c: i for i, c in enumerate(used)}
            # 源行首列是 idcol(非 None 时),故目标列的下标要 +1
            off = lambda c: idx[c] + (0 if idcol is None or idx[c] == 0 else 1)
            patched = []
            for r in src_rows:
                vals = list(r)
                # 两类转换分开计数:混在一起会让 [known] 打出
                # 「551 行源侧  为 NULL」这种没有列名的句子,读者无从判断是哪一种。
                for col, fallback in fb.items():
                    if col in idx and vals[off(col)] is None:
                        vals[off(col)] = fallback
                        normalized += 1
                for col, token in sentinel.items():
                    if col in idx and vals[off(col)] == token:
                        vals[off(col)] = None
                        sentinel_hits += 1
                patched.append(tuple(vals))
            src_rows = patched
            if normalized:
                FILL_REPORT[target] = FILL_REPORT.get(target, 0) + normalized
            if sentinel_hits:
                SENTINEL_REPORT[target] = SENTINEL_REPORT.get(target, 0) + sentinel_hits

        pks, mks = keyset(src_rows, idcol), keyset(my_rows, idcol)
        missing = sorted(pks - mks)
        extra = len(mks - pks)

        def digest(rows):
            h = hashlib.sha256()
            for r in rows:
                h.update('\x1f'.join(norm(v) for v in r).encode('utf-8'))
            return h.hexdigest()[:12]

        ph, mh = digest(src_rows), digest(my_rows)
        # 目标多出 dev 库自己的测试行时,整体哈希必然不同,此时只比对交集
        hash_state = '一致'
        if extra and not missing:
            common_p = [r for r in src_rows if (r[0] if idcol else (r[0], r[1])) in pks & mks]
            common_m = [r for r in my_rows if (r[0] if idcol else (r[0], r[1])) in pks & mks]
            ph, mh = digest(common_p), digest(common_m)
            hash_state = '一致(交集)' if ph == mh else f'不一致(交集 {ph}≠{mh})'
        elif ph == mh:
            hash_state = '一致'
        else:
            hash_state = f'不一致 {ph}≠{mh}'

        if missing:
            failed.append((target, f'缺迁 {len(missing)} 个键: {missing[:5]}'))
        if hash_state.startswith('不一致'):
            failed.append((target, f'内容哈希{hash_state}'))
        if extra:
            warned.append((target, f'目标多出 {extra} 行(v3 自有测试/新增数据,非丢数)'))

        print(f'{target:<40} {len(src_rows):>6} {len(my_rows):>6} {len(missing):>6}  {hash_state}')
        if verbose and hash_state.startswith('不一致'):
            for r in (my_rows or [])[:5]:
                print(f'    目标行样本: {r}')

    # A-2:L3 覆盖度自查——把「哪些迁移列没有被内容哈希验过」显式打出来。
    # CHECKS 每表只取若干关键列,合计只覆盖迁移列的一部分(比例由下面现算,别写死在注释里——
    # 写死过一次就与实际脱节过),而文件头声称 L3 抓的是「列映射写反、JSON 序列化错」
    # ——那只对被采样的列成立。
    # 未覆盖的列里就包含批11 整批存在的理由(llm_prompt/llm_response/validation_result):
    # 这几列的 MAPS 或转换器若有错,四层判据全绿而成果表的 LLM 上下文静默损坏,
    # 且切流单向不可逆。覆盖率不报 = 「没验」这件事默认看不见。
    if VERBOSE_COVERAGE:
        total_mapped = covered = 0
        gaps = []
        for target, _src, _idcol, cols in CHECKS:
            mapped = [v3 for _p, v3, _c in _etl.V2.MAPS.get(target, [])]
            if not mapped:
                continue
            not_hashed = [c for c in mapped if c not in cols]
            total_mapped += len(mapped)
            covered += len(mapped) - len(not_hashed)
            if not_hashed:
                gaps.append(f'{target}: {", ".join(not_hashed)}')
        pct = covered / total_mapped * 100 if total_mapped else 0
        state = '全覆盖' if pct >= 100 else f'**仅 {pct:.0f}%**'
        print(f'[cover] L3 内容哈希覆盖 {covered}/{total_mapped} 个迁移列({state})')
        if FULL and pct < 100:
            print('[cover] --full 下仍不到 100% 的只有两类:① id 列(刻意排除,L2 已在比 id 集合);'
                  '② 源表根本没有的列(见下方 [uncovered])。这两类都不是漏验。')
        if gaps:
            print('[cover] 未被内容哈希验过的列(写错不会被任何一层发现):')
            for g in gaps:
                print(f'    - {g}')

    # L4 框架列核验:行数与业务字段都对得上,不代表应用看得见这行。
    # 芋道按 `tenant_id = 当前租户` 过滤,一行 tenant_id=0 就是「迁进来了但永远查不到」,
    # 而 L1/L2/L3 会全绿——批11 真的踩过:框架列漏写,落回 DDL 默认 tenant_id=0,
    # 2895 行成果数据全部对应用不可见,而当时对账报的是「齐平」。
    print()
    frame_bad = []
    for target, _src, _idcol, _cols in CHECKS:
        # 判据只管**ETL 写入的行**(creator='etl'):v3 库里本来就可能有它自己的
        # 测试行(tenant_id 不为 1),那是 v3 的事,不该由迁移门禁来背锅。
        myc.execute(f"SELECT COUNT(*) FROM `{target}` "
                    f"WHERE creator = 'etl' AND (tenant_id <> 1 OR deleted <> %s)", (bytes([0]),))
        bad = myc.fetchone()[0]
        if bad:
            frame_bad.append((target, f'ETL 写入的行里有 {bad} 行 tenant_id<>1 或 deleted<>0 —— '
                                     f'这类行对应用不可见(芋道按 tenant_id 过滤)'))

    for t, n in FILL_REPORT.items():
        cols_ = ', '.join(NOTNULL_FALLBACK.get(t, {}))
        print(f'[known] {t}: {n} 行源侧 {cols_} 为 NULL,ETL 按已声明的 NOTNULL_FALLBACK '
              f'补值后写入(目标列 NOT NULL 所致),已归一后参与哈希比对,非数据丢失')
    for t, cols_ in uncovered:
        print(f'[uncovered] {t}: 源表无 {", ".join(cols_)} 列(V1 早于该列引入),'
              f'本层无从比对;ETL 按 NULL 迁,目标列可空')
    for t, n in SENTINEL_REPORT.items():
        print(f'[known] {t}: {n} 行源侧数字列是角色名哨兵,ETL 按 v2 的 PG 强类型口径置 NULL,'
              f'已归一后参与哈希比对,身份由 reviewer_type/operator_code 承载,非数据丢失')
    for t, msg in warned:
        print(f'[warn] {t}: {msg}')
    for t, msg in failed + frame_bad:
        print(f'[FAIL] {t}: {msg}')
    src_con.close()
    my.close()
    if failed or frame_bad:
        print(f'\n[FAIL] {len(failed) + len(frame_bad)} 项对账不通过 —— 切流闸门不能开')
        return 1
    print('\n[ok] 对账齐平(无丢数、无内容不一致、框架列 tenant_id/deleted 正常)'
          + (f';{len(warned)} 张表目标侧多出 v3 自有数据(已按交集核验)' if warned else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
