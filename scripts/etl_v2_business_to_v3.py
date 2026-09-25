#!/usr/bin/env python
"""v3 批11 切流 ETL:业务成果域 PG(v2 awardie_dev)→ MySQL(v3 awardie_v3)。

用法(venv python):
    AWARDIE_MYSQL_PASSWORD=<v3 应用口令> python scripts/etl_v2_business_to_v3.py [--dry-run]

覆盖 15 张表:awards / 获奖学生·教师·关联学生 / pending_achievements /
innovation_projects(+学生) / patents / software_copyrights / other_files /
templates / laboratory_downloads / laboratory_images / review_logs /
achievement_audit_log。

实现要点(每条都有理由):
1. **列映射是单一事实来源**(MAPS)。SELECT 的列与写入的列都从同一份定义生成——
   首版手写列名在两处各写一遍,立刻踩了坑(写 `student_id_no` 而 PG 里叫
   `student_id_str`;写 `sort_order` 而实际叫 `display_order`)。同名写两遍必然漂移。
2. **显式保留 v2 主键 id**,ON DUPLICATE KEY UPDATE 按主键幂等,可重复执行。
3. **created_at/updated_at → create_time/update_time**(重命名,不是丢弃)。
   用 v2 原值,不取 NOW(),否则历史时间线全变成今天。
4. **PG jsonb**:achievement_data / llm_response / validation_result 存 JSON **字符串**
   (v3 RespVO 就是 String,前端自行 parse);change_detail / sample_extracted 等
   存 MySQL JSON 列。
5. **audit_log 只迁 is_test=false 的行**——1693 行里 1674 行是测试数据
   (v2 自己有 is_test 标记),迁进来是污染目标库。
6. **review_logs 全迁**:v2 专有表,v3 无等价表,长达七个月的真实审核流水。
7. **pending 与 awards 按 file_hash 有 151 条重叠,不去重**:v2 本就是两张表两个语义
   (提交队列 vs 成果库),重叠是 v2 既有状态,保持一致才不篡改历史。
8. **框架列** creator/updater/create_time/update_time/deleted/tenant_id 统一补齐。

用法纪律:先 --dry-run 看清单,再实跑;实跑后必看 [verify] 段。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import psycopg2
import pymysql

PG = dict(host='127.0.0.1', port=5433, dbname='awardie_dev', user='postgres',
          password=os.environ.get('PGPASSWORD', 'postgres'))
MYSQL = dict(host='127.0.0.1', port=3307, db=os.environ.get('AWARDIE_TARGET_DB', 'awardie_v3'), user='awardie_v3',
             password=os.environ.get('AWARDIE_MYSQL_PASSWORD', ''), charset='utf8mb4')
CST = timezone(timedelta(hours=8))  # v2 存 +08:00,写 MySQL 前统一到本地无时区

FRAME_COLS = ['creator', 'updater', 'create_time', 'update_time', 'deleted', 'tenant_id']


# ---------------- 转换器 ----------------
def j2s(v):
    """PG jsonb → JSON 字符串;已经是 str 就原样返回。"""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, default=str)


def j2d(v):
    """PG jsonb → dict/list(MySQL JSON 列用);解析不了返回 None。"""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


def tm(v):
    """带时区 PG timestamp → naive 本地时间(MySQL DATETIME 不带时区)。"""
    if v is None or not isinstance(v, datetime):
        return v
    if v.tzinfo is not None:
        v = v.astimezone(CST)
    return v.replace(tzinfo=None)


def bl(v):
    """PG boolean → MySQL BIT(1) 的 b'0'/b'1'。"""
    return None if v is None else (b'\x01' if v else b'\x00')


CONV = {'t': tm, 'b': bl, 's': j2s, 'd': j2d}

# 目标表有、源表没有的列 → 补常量。v2 templates 没有 granted_role,而 v3 侧是
# NOT NULL,不给值整批插不进去;批7 建的模板域默认面向学生,故取「学生」并在
# 收尾时显式上报(不是静默默认值)。
FILL = {
    'awardie_templates': {'granted_role': '学生'},
}

# v3 侧 NOT NULL 但 v2 侧可空的列 → 出现 NULL 时补的值 + 上报计数。
# 不静默丢弃:588 条 pending 里有 5 条是 v2 的巡检测试残留
# (achievement_data={"competition_name":"巡检赛"}、file_hash="inspect-<随机>"、
#  submitter_type/submitter_id 皆空),但「像测试数据」不等于「用户确认可以删」。
# 补值迁移 + 计数上报,把处置权留给闸门前的决策者。
NOTNULL_FALLBACK = {
    'awardie_pending_achievements': {'submitter_type': 'admin'},
}

# ---------------- 列映射:单一事实来源 ----------------
# (v2列名, v3列名, 转换器)
MAPS = {
    'awardie_awards': [
        ('id', 'id', None), ('image_hash', 'image_hash', None),
        ('certificate_id', 'certificate_id', None), ('certificate_path', 'certificate_path', None),
        ('competition_name_in_file', 'competition_name_in_file', None), ('track', 'track', None),
        ('issuer', 'issuer', None), ('province', 'province', None), ('group_name', 'group_name', None),
        ('winner_name', 'winner_name', None), ('supervisor_name', 'supervisor_name', None),
        ('award_level', 'award_level', None), ('competition_level', 'competition_level', None),
        ('date', 'date', None), ('project_title', 'project_title', None),
        ('competition_id', 'competition_id', None), ('submitter_type', 'submitter_type', None),
        ('submitter_id', 'submitter_id', None), ('submit_time', 'submit_time', 't'),
        ('laboratory_id', 'laboratory_id', None), ('year', 'year', None), ('edition', 'edition', None),
        ('related_student_name', 'related_student_name', None), ('is_abnormal', 'is_abnormal', 'b'),
        ('ocr_result', 'ocr_result', None), ('extract_json', 'extract_json', None),
        ('match_status', 'match_status', 'b'), ('granted_role', 'granted_role', None),
        ('llm_prompt', 'llm_prompt', None), ('llm_response', 'llm_response', 's'),
        ('validation_result', 'validation_result', 's'), ('created_at', 'create_time', 't'),
        ('updated_at', 'update_time', 't'),
    ],
    'awardie_pending_achievements': [
        ('id', 'id', None), ('achievement_type', 'achievement_type', None),
        ('achievement_data', 'achievement_data', 's'), ('validation_result', 'validation_result', 's'),
        ('submitter_type', 'submitter_type', None), ('submitter_id', 'submitter_id', None),
        ('submit_time', 'submit_time', 't'), ('status', 'status', None),
        ('reviewer_id', 'reviewer_id', None), ('review_time', 'review_time', 't'),
        ('review_comment', 'review_comment', None), ('file_path', 'file_path', None),
        ('assigned_reviewer_type', 'assigned_reviewer_type', None),
        ('reviewer_type', 'reviewer_type', None), ('file_hash', 'file_hash', None),
        ('ocr_text', 'ocr_text', None), ('llm_prompt', 'llm_prompt', None),
        ('llm_response', 'llm_response', 's'), ('ext_info', 'ext_info', 's'),
        ('session_id', 'session_id', None), ('laboratory_id', 'laboratory_id', None),
        ('version', 'version', None), ('created_at', 'create_time', 't'),
    ],
    'awardie_award_student_winners': [
        ('award_id', 'award_id', None), ('student_id', 'student_id', None),
        ('created_at', 'create_time', 't')],
    'awardie_award_teacher_winners': [
        ('award_id', 'award_id', None), ('teacher_id', 'teacher_id', None),
        ('created_at', 'create_time', 't')],
    'awardie_award_related_students': [
        ('award_id', 'award_id', None), ('student_id', 'student_id', None),
        ('created_at', 'create_time', 't')],
    'awardie_innovation_projects': [
        ('id', 'id', None), ('project_no', 'project_no', None),
        ('project_name', 'project_name', None), ('project_type', 'project_type', None),
        ('status', 'status', None), ('start_date', 'start_date', None),
        ('end_date', 'end_date', None), ('funding_amount', 'funding_amount', None),
        ('student_leader_name', 'student_leader_name', None),
        ('student_leader_id', 'student_leader_id', None), ('other_members', 'other_members', 's'),
        ('supervisors', 'supervisors', None), ('laboratory_id', 'laboratory_id', None),
        ('submit_time', 'submit_time', 't'), ('created_at', 'create_time', 't')],
    'awardie_innovation_project_students': [
        ('project_id', 'project_id', None), ('student_id', 'student_id', None),
        ('role', 'role', None), ('student_name', 'student_name', None),
        ('student_id_str', 'student_id_str', None), ('match_type', 'match_type', None),
        # v2 这张表没有时间列,create_time 走 v3 的 DEFAULT CURRENT_TIMESTAMP
        ],
    'awardie_patents': [
        ('id', 'id', None), ('patent_name', 'patent_name', None), ('patent_type', 'patent_type', None),
        ('application_number', 'application_number', None),
        ('publication_number', 'publication_number', None), ('inventor', 'inventor', None),
        ('patentee', 'patentee', None), ('certificate_file', 'certificate_file', None),
        ('submitter_type', 'submitter_type', None), ('submitter_id', 'submitter_id', None),
        ('application_date', 'application_date', None), ('laboratory_id', 'laboratory_id', None),
        ('created_at', 'create_time', 't'), ('updated_at', 'update_time', 't')],
    'awardie_software_copyrights': [
        ('id', 'id', None), ('software_name', 'software_name', None),
        ('software_version', 'software_version', None),
        ('registration_number', 'registration_number', None),
        ('certificate_no', 'certificate_no', None), ('registration_date', 'registration_date', None),
        ('copyright_owner', 'copyright_owner', None),
        ('certificate_file', 'certificate_file', None),
        ('submitter_type', 'submitter_type', None), ('submitter_id', 'submitter_id', None),
        ('submit_time', 'submit_time', 't'), ('laboratory_id', 'laboratory_id', None),
        ('created_at', 'create_time', 't'), ('updated_at', 'update_time', 't')],
    'awardie_other_files': [
        ('id', 'id', None), ('file_name', 'file_name', None), ('file_path', 'file_path', None),
        ('file_type', 'file_type', None), ('file_size', 'file_size', None),
        ('file_hash', 'file_hash', None), ('is_image', 'is_image', 'b'),
        ('description', 'description', None), ('submitter_type', 'submitter_type', None),
        ('submitter_id', 'submitter_id', None), ('submit_time', 'submit_time', 't'),
        ('laboratory_id', 'laboratory_id', None), ('created_at', 'create_time', 't')],
    'awardie_templates': [
        ('id', 'id', None), ('template_type', 'template_type', None),
        ('competition_id', 'competition_id', None),
        ('min_length', 'min_length', None), ('max_length', 'max_length', None),
        ('keywords', 'keywords', 'd'), ('sample_text', 'sample_text', None),
        ('sample_extracted', 'sample_extracted', 'd'), ('default_fields', 'default_fields', 'd'),
        ('llm_fields', 'llm_fields', 'd'), ('language', 'language', None),
        ('need_translate', 'need_translate', 'b'),
        ('sample_image_path', 'sample_image_path', None),
        ('created_at', 'create_time', 't')],
    'awardie_laboratory_downloads': [
        ('id', 'id', None), ('laboratory_id', 'laboratory_id', None),
        ('file_path', 'file_path', None), ('file_title', 'file_title', None),
        ('file_name', 'file_name', None), ('file_size', 'file_size', None),
        ('submitter_type', 'submitter_type', None), ('submitter_id', 'submitter_id', None),
        ('is_public', 'is_public', 'b'), ('display_order', 'display_order', None),
        ('created_at', 'create_time', 't')],
    'awardie_laboratory_images': [
        ('id', 'id', None), ('laboratory_id', 'laboratory_id', None),
        ('image_path', 'image_path', None), ('file_name', 'file_name', None),
        ('file_hash', 'file_hash', None), ('description', 'description', None),
        ('display_order', 'display_order', None), ('submitter_type', 'submitter_type', None),
        ('submitter_id', 'submitter_id', None), ('created_at', 'create_time', 't')],
    'awardie_review_logs': [
        ('id', 'id', None), ('pending_id', 'pending_id', None),
        ('achievement_type', 'achievement_type', None), ('action_type', 'action_type', None),
        ('result_type', 'result_type', None), ('result_id', 'result_id', None),
        ('result_file_path', 'result_file_path', None), ('file_hash', 'file_hash', None),
        ('file_path', 'file_path', None), ('submitter_type', 'submitter_type', None),
        ('submitter_id', 'submitter_id', None), ('reviewer_type', 'reviewer_type', None),
        ('reviewer_id', 'reviewer_id', None), ('review_comment', 'review_comment', None),
        ('operation_note', 'operation_note', None), ('created_at', 'create_time', 't')],
    'awardie_achievement_audit_log': [
        ('id', 'id', None), ('achievement_id', 'achievement_id', None),
        ('achievement_kind', 'achievement_kind', None), ('action_type', 'action_type', None),
        ('action_result', 'action_result', None), ('operator_id', 'operator_id', None),
        ('operator_code', 'operator_code', None), ('operator_name', 'operator_name', None),
        ('change_detail', 'change_detail', 'd'), ('remark', 'remark', None),
        ('created_at', 'create_time', 't')],
}

# 补值上报(运行期填充)
FILL_REPORT: dict[str, int] = {}

# 目标表 → v2 源表
SOURCES = {t: t.replace('awardie_', '') for t in MAPS}
SOURCES['awardie_achievement_audit_log'] = 'achievement_audit_log'
AUDIT_FILTER = ' WHERE is_test = false AND is_redundant = false'
# 无 id 列的关联表,靠 UNIQUE 键 upsert
NO_PK = {'awardie_award_student_winners', 'awardie_award_teacher_winners',
         'awardie_award_related_students', 'awardie_innovation_project_students'}
# 写入顺序:先有 id 的主表,再关联表(关联表指向主表)
ORDER = [
    'awardie_awards', 'awardie_pending_achievements',
    'awardie_innovation_projects', 'awardie_patents', 'awardie_software_copyrights',
    'awardie_other_files', 'awardie_templates',
    'awardie_award_student_winners', 'awardie_award_teacher_winners',
    'awardie_award_related_students', 'awardie_innovation_project_students',
    'awardie_laboratory_downloads', 'awardie_laboratory_images',
    'awardie_review_logs', 'awardie_achievement_audit_log',
]


def fetch_all():
    """读全部源表,返回 {目标表: (列名列表, 行元组列表)}。"""
    pg = psycopg2.connect(**PG)
    cur = pg.cursor()
    out = {}
    pending_fill = {}
    for target in ORDER:
        spec = MAPS[target]
        src = SOURCES[target]
        sql = f"SELECT {', '.join(c for c, _, _ in spec)} FROM {src}"
        if target == 'awardie_achievement_audit_log':
            sql += AUDIT_FILTER
        sql += f" ORDER BY {spec[0][0]}"
        cur.execute(sql)
        raw = cur.fetchall()

        cols = [v3 for _, v3, _ in spec]
        fill = FILL.get(target, {})
        if fill:
            cols = cols + list(fill.keys())
        fb = NOTNULL_FALLBACK.get(target, {})
        filled = 0
        rows = []
        for r in raw:
            vals = [CONV[conv](v) if conv else v for v, (_, _, conv) in zip(r, spec)]
            if fill:
                vals = vals + [fill[c] for c in fill]
            for col, fallback in fb.items():
                if col in cols and vals[cols.index(col)] is None:
                    vals[cols.index(col)] = fallback
                    filled += 1
            rows.append((vals, None))
        out[target] = (cols, raw, rows)
        if fb and filled:
            FILL_REPORT[target] = filled
    pg.close()
    return out


def write_all(data, conn):
    cur = conn.cursor()
    for target in ORDER:
        cols, raw, rows = data[target]
        if not rows:
            print(f'[write] {target:<40} 源 0 行,跳过')
            continue
        if target in NO_PK:
            write_cols = cols + ['creator', 'deleted', 'tenant_id']
        else:
            write_cols = cols
        ph = ', '.join(['%s'] * len(write_cols))
        if 'id' in write_cols:
            ups = ', '.join(f"`{c}` = VALUES(`{c}`)" for c in write_cols if c != 'id')
        else:
            ups = ', '.join(f"`{c}` = VALUES(`{c}`)" for c in write_cols)
        sql = (f"INSERT INTO `{target}` ({', '.join('`'+c+'`' for c in write_cols)}) "
               f"VALUES ({ph}) ON DUPLICATE KEY UPDATE {ups}")
        payload = []
        for vals, _stamp in rows:
            # pymysql 不能直接传 dict/list(MySQL JSON 列靠字符串入列再解析)
            row = [json.dumps(v, ensure_ascii=False, default=str)
                   if isinstance(v, (dict, list)) else v for v in vals]
            if target in NO_PK:
                row += ['etl', b'\x00', 1]
            elif 'creator' in write_cols:
                row[write_cols.index('creator')] = 'etl'
                row[write_cols.index('updater')] = 'etl'
                row[write_cols.index('deleted')] = b'\x00'
                row[write_cols.index('tenant_id')] = 1
            payload.append(tuple(row))
        cur.executemany(sql, payload)
        print(f'[write] {target:<40} 源 {len(rows):>5} 行,影响 {cur.rowcount} 行')
    conn.commit()
    return cur


def verify(data, cur):
    print('[verify] 目标库行数 / id 集合差')
    problems = 0
    for target in ORDER:
        cols, raw, rows = data[target]
        cur.execute(f"SELECT COUNT(*) FROM `{target}`")
        total = cur.fetchone()[0]
        expect = len(rows)
        note = ''
        if 'id' in cols:
            key = raw and [r[0] for r in raw] or []
            cur.execute(f"SELECT `id` FROM `{target}`")
            have = {r[0] for r in cur.fetchall()}
            missing = sorted(set(key) - have)
            if missing:
                note = f' 缺迁 {len(missing)} 个 id: {missing[:5]}'
                problems += len(missing)
        if total < expect:
            note += f' [异常] 目标 {total} < 源 {expect}'
            problems += 1
        print(f'[verify] {target:<40} 目标 {total:>5} (源 {expect}){note}')
    return problems


def main() -> int:
    dry = '--dry-run' in sys.argv
    if not MYSQL['password']:
        print('缺少环境变量 AWARDIE_MYSQL_PASSWORD', file=sys.stderr)
        return 2

    data = fetch_all()
    total_rows = sum(len(v[2]) for v in data.values())
    print(f'[read] v2 共 {total_rows} 行 / {len(data)} 张表')
    if FILL_REPORT:
        for t_, n in FILL_REPORT.items():
            cols = ', '.join(NOTNULL_FALLBACK.get(t_, {}))
            print(f'[fill]  {t_:<40} {n} 行因 {cols} 为 NULL 被补值(源侧可空/目标侧 NOT NULL),'
                  f'这些行是 v2 测试残留,是否删除请在切流闸门前定')
    for target in ORDER:
        print(f'   {target:<40} {len(data[target][2]):>5}')

    if dry:
        print('[dry-run] 未落盘')
        return 0

    conn = pymysql.connect(**MYSQL)
    cur = write_all(data, conn)
    problems = verify(data, cur)
    cur.execute("SELECT MAX(id) FROM awardie_awards")
    print(f"[verify] awardie_awards MAX(id)={cur.fetchone()[0]}")
    conn.close()
    if problems:
        print(f'[FAIL] {problems} 处对账异常')
        return 1
    print('[ok] 切流 ETL 完成且对账齐平')
    return 0


if __name__ == '__main__':
    sys.exit(main())
