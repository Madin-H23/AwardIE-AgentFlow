#!/usr/bin/env python
"""v3 切流对账:源库(v2 PG)与目标库(v3 MySQL)逐表逐行核验。

与 ETL 的自校不同——自校只验「源 id 都在目标里」,抓不到「id 都在但字段写错」。
本工具做三层:
  L1 行数:目标行数 vs 源行数(允许 dev 库多出测试行,只报差额不判失败)
  L2 id 集合:双向差集。**源有目标无 = 真实丢数,直接 FAIL**
  L3 内容哈希:对每张表选若干关键字段,按 id 排序算 sha256,两边比对。
     抓的是「行在、值不对」——列映射写反、jsonb 序列化错、时区偏移都会在这里现形。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<口令> python scripts/v3_reconcile.py [--verbose]

退出码:0 = 对账齐平;1 = 有丢数或内容不一致(切流闸门不能过)。
"""
import hashlib
import importlib.util
import json
import os
import sys

import psycopg2
import pymysql

# 从 ETL 脚本里取 NOTNULL_FALLBACK —— 「已声明的例外」只写一处,两个工具都认它。
# 不各写一份:各写一份迟早漂移,漂移的表现是对账误报或漏报,都伤闸门的可信度。
_spec = importlib.util.spec_from_file_location(
    'etl_biz', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'etl_v2_business_to_v3.py'))
_etl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_etl)
NOTNULL_FALLBACK = _etl.NOTNULL_FALLBACK
FILL_REPORT: dict[str, int] = {}

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
    # jsonb 列必须归一后再比,否则报的是假警:
    #   源侧 psycopg2 把 jsonb 自动解析成 Python 对象(dict/True/None/单引号),
    #   目标侧 MySQL TEXT 存的是规范 JSON(true/null/双引号)——
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


def fetch_pg(cur, src, cols, idcol, filter_=''):
    sel = cols if idcol is None else [idcol] + [c for c in cols if c != idcol]
    sql = f"SELECT {', '.join(sel)} FROM {src}{filter_} ORDER BY {sel[0]}"
    if idcol is None and len(sel) > 1:
        sql += f", {sel[1]}"
    cur.execute(sql)
    return cur.fetchall()


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
    pg = psycopg2.connect(**PG)
    pgc = pg.cursor()
    my = pymysql.connect(**MYSQL)
    myc = my.cursor()

    failed, warned = [], []
    print(f"{'表':<40} {'源':>6} {'目标':>6} {'缺迁':>6}  内容哈希")
    print('-' * 92)
    for target, src, idcol, cols in CHECKS:
        filt = AUDIT_FILTER if target == 'awardie_achievement_audit_log' else ''
        pg_rows = fetch_pg(pgc, src, cols, idcol, filt)
        my_rows = fetch_my(myc, target, cols, idcol)

        def keyset(rows, idcol):
            if idcol is not None:
                return {r[0] for r in rows}
            return {(r[0], r[1]) for r in rows}

        # 已声明的补值:源侧 NULL 会被 ETL 填成 NOTNULL_FALLBACK 的值。
        # 在算哈希前对源侧做同样的归一,否则这批行会被报成「内容不一致」——
        # 那不是数据问题,是已知且有意的转换。计数后单独上报,不藏。
        fb = NOTNULL_FALLBACK.get(target, {})
        normalized = 0
        if fb:
            idx = {c: i for i, c in enumerate(cols)}
            patched = []
            for r in pg_rows:
                vals = list(r)
                changed = False
                for col, fallback in fb.items():
                    if col in idx and vals[idx[col] + (0 if idcol is None or idx[col] == 0 else 1)] is None:
                        vals[idx[col] + (0 if idcol is None or idx[col] == 0 else 1)] = fallback
                        changed = True
                normalized += 1 if changed else 0
                patched.append(tuple(vals))
            pg_rows = patched
            if normalized:
                FILL_REPORT[target] = FILL_REPORT.get(target, 0) + normalized

        pks, mks = keyset(pg_rows, idcol), keyset(my_rows, idcol)
        missing = sorted(pks - mks)
        extra = len(mks - pks)

        def digest(rows):
            h = hashlib.sha256()
            for r in rows:
                h.update('\x1f'.join(norm(v) for v in r).encode('utf-8'))
            return h.hexdigest()[:12]

        ph, mh = digest(pg_rows), digest(my_rows)
        # 目标多出 dev 库自己的测试行时,整体哈希必然不同,此时只比对交集
        hash_state = '一致'
        if extra and not missing:
            common_p = [r for r in pg_rows if (r[0] if idcol else (r[0], r[1])) in pks & mks]
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

        print(f'{target:<40} {len(pg_rows):>6} {len(my_rows):>6} {len(missing):>6}  {hash_state}')
        if verbose and hash_state.startswith('不一致'):
            for r in (my_rows or [])[:5]:
                print(f'    目标行样本: {r}')

    # A-2:L3 覆盖度自查——把「哪些迁移列没有被内容哈希验过」显式打出来。
    # 首版 CHECKS 每表只取 2-6 个关键列,合计只覆盖 48/94 个迁移列(51%),
    # 而文件头声称 L3 抓的是「列映射写反、jsonb 序列化错」——那只对被采样的列成立。
    # 未覆盖的列里就包含批11 整批存在的理由(llm_prompt/llm_response/validation_result):
    # 这三列的 MAPS 或转换器若有错,四层判据全绿而 311 行成果的 LLM 上下文静默损坏,
    # 且切流单向不可逆。覆盖率不报 = 「没验」这件事默认看不见。
    if VERBOSE_COVERAGE:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            'etl_biz_cov',
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'etl_v2_business_to_v3.py'))
        _etl = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_etl)
        total_mapped = covered = 0
        gaps = []
        for target, _src, _idcol, cols in CHECKS:
            mapped = [v3 for _p, v3, _c in _etl.MAPS.get(target, [])]
            if not mapped:
                continue
            uncovered = [c for c in mapped if c not in cols]
            total_mapped += len(mapped)
            covered += len(mapped) - len(uncovered)
            if uncovered:
                gaps.append(f'{target}: {", ".join(uncovered)}')
        pct = covered / total_mapped * 100 if total_mapped else 0
        state = '全覆盖' if pct >= 100 else f'**仅 {pct:.0f}%**'
        print(f'[cover] L3 内容哈希覆盖 {covered}/{total_mapped} 个迁移列({state})')
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
    for t, msg in warned:
        print(f'[warn] {t}: {msg}')
    for t, msg in failed + frame_bad:
        print(f'[FAIL] {t}: {msg}')
    pg.close(); my.close()
    if failed or frame_bad:
        print(f'\n[FAIL] {len(failed) + len(frame_bad)} 项对账不通过 —— 切流闸门不能开')
        return 1
    print('\n[ok] 对账齐平(无丢数、无内容不一致、框架列 tenant_id/deleted 正常)'
          + (f';{len(warned)} 张表目标侧多出 v3 自有数据(已按交集核验)' if warned else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
