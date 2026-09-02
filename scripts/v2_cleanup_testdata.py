# -*- coding: utf-8 -*-
"""v2 测试数据清理(Fix-A,一次性执行前请先阅读统计输出)。

背景:Fix-A 之前集成测试直连开发库 awardie_dev,17 轮 mvn test 与浏览器
手动测试在真实数据上累积了提交/物化/用户创建。本脚本:
  1. pg_dump 全量备份 awardie_dev → database/backups/
  2. 输出待删清单统计(分项行数)
  3. 执行清理(仅删测试痕迹行,保留迁移基线与三真实账号)
  4. 清理前后计数对照

保留口径:
  - pending_achievements:保留 created_at <= '2026-08-29' 的迁移行
  - awards 及关联:保留 id <= 迁移基线最大 id
  - users:保留全部迁移行(id <= 迁移基线最大 id),删除之后创建的测试账号

用法:python scripts/v2_cleanup_testdata.py --apply   (不带 --apply 仅预览)
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

PG = r"D:/Develop/tools/pg16-portable/pg16/pgsql/bin/psql.exe"
DUMP = r"D:/Develop/tools/pg16-portable/pg16/pgsql/bin/pg_dump.exe"
CONN = ["-p", "5433", "-U", "postgres", "-d", "awardie_dev", "-t", "-A", "-c"]
BACKUP_DIR = r"D:/Develop/AI 应用开发/AI应用开发项目/AwardIE-AgentFlow/database/backups"
CUTOFF = "2026-08-29"


def q(sql):
    # 经 UTF-8 临时文件传 SQL:Windows 命令行参数走 GBK 管道,内嵌中文会被破坏
    # (本坑第三次出现,根治于此)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sql", encoding="utf-8", delete=False) as f:
        f.write(sql)
        tmp = f.name
    try:
        r = subprocess.run([PG, "-p", "5433", "-U", "postgres", "-d", "awardie_dev",
                            "-t", "-A", "-f", tmp], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    finally:
        os.unlink(tmp)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()


def rows(sql):
    return [line.split("|") for line in q(sql).splitlines() if line]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际执行清理(默认仅预览)")
    ap.add_argument("--tagged", action="store_true",
                    help="标记口径:仅删含测试标记(E2E/BF/时间线等)的行——供 E2E teardown 使用,保护真实提交")
    args = ap.parse_args()

    # 基线最大 award id(迁移行)
    baseline_max = q("SELECT COALESCE(MAX(id), 0) FROM awards WHERE created_at < '2026-08-29'")
    print(f"迁移基线最大 award id = {baseline_max}")

    # --tagged 模式:只删带测试标记的行(OCR 审查 medium 修复:防日期口径误删真实提交)。
    # 标记覆盖:E2E/BF 前缀、时间线/撤回/教师提交 E2E、批量导入、种子、TRACER、巡检/回归/测试字样。
    tagged_pending = (" AND (achievement_data::text LIKE '%E2E%' OR achievement_data::text LIKE '%BF%'"
                      " OR achievement_data::text LIKE '%批量导入%' OR achievement_data::text LIKE '%种子%'"
                      " OR achievement_data::text LIKE '%TRACER%' OR file_path LIKE '%batch-%'"
                      " OR file_path LIKE '%tl-%' OR file_path LIKE '%bf-%' OR file_path LIKE '%teacher-e2e%')")
    tagged_awards = (" AND (competition_name_in_file LIKE '%E2E%' OR competition_name_in_file LIKE '%BF%'"
                     " OR competition_name_in_file LIKE '%批量导入%' OR competition_name_in_file LIKE '%种子%'"
                     " OR competition_name_in_file LIKE '%TRACER%')")
    tagged_where_pending = f" created_at > '{CUTOFF}'" + (tagged_pending if args.tagged else "")
    tagged_where_awards = f" id > {baseline_max}" + (tagged_awards if args.tagged else "")
    if args.tagged:
        print("[tagged 模式] 仅清理带测试标记的行(真实提交不受影响)")

    # G2:patents/software/innovation/other 四表基线=迁移装载日(2026-08-29)之前;
    # 迁移行保留 v1 历史 created_at(01-29/08-22),08-30 后均为 v2 测试/E2E 残留。
    # tagged 模式加名称标记双保险;v1 权威口径:patents 0/software 1/innovation 20/other 1。
    FOUR_BASE = "2026-08-30"
    marker = "(E2E|BF|批量|种子|TRACER|测试|时间线|撤回|教师提交)"
    four = [
        ("patents", "patent_name", "patents_new"),
        ("software_copyrights", "software_name", "software_new"),
        ("innovation_projects", "project_name", "innovation_new"),
        ("other_files", "file_name", "other_new"),
    ]
    four_where = {}
    for tbl, col, _ in four:
        base = f" created_at > '{FOUR_BASE}'"
        four_where[tbl] = base + (f" AND {col} ~ '{marker}'" if args.tagged else "")
    # stats f-string 用的展开变量
    four_where_patents = four_where["patents"]
    four_where_software_copyrights = four_where["software_copyrights"]
    four_where_innovation_projects = four_where["innovation_projects"]
    four_where_other_files = four_where["other_files"]

    # SQL 内禁用中文(Windows psql 管道 GBK 编码会破坏 UTF8);中文标签在 Python 侧映射
    stats = rows(f"""
        SELECT 'pending_new', COUNT(*) FROM pending_achievements WHERE{tagged_where_pending}
        UNION ALL SELECT 'awards_new', COUNT(*) FROM awards WHERE{tagged_where_awards}
        UNION ALL SELECT 'student_winners_new', COUNT(*) FROM award_student_winners WHERE award_id > {baseline_max}
        UNION ALL SELECT 'supervisors_new', COUNT(*) FROM award_supervisors WHERE award_id > {baseline_max}
        UNION ALL SELECT 'audit_new', COUNT(*) FROM achievement_audit_log WHERE created_at > '{CUTOFF}'
        UNION ALL SELECT 'patents_new', COUNT(*) FROM patents WHERE{four_where_patents}
        UNION ALL SELECT 'software_new', COUNT(*) FROM software_copyrights WHERE{four_where_software_copyrights}
        UNION ALL SELECT 'innovation_new', COUNT(*) FROM innovation_projects WHERE{four_where_innovation_projects}
        UNION ALL SELECT 'other_new', COUNT(*) FROM other_files WHERE{four_where_other_files}
        UNION ALL SELECT 'users_new', COUNT(*) FROM users
            WHERE id > (SELECT COALESCE(MAX(id), 0) FROM users WHERE created_at < '2026-08-29')
              AND login_code NOT IN ('admin', '212306413', '02110606')
    """)
    zh = {
        'pending_new': 'pending_achievements(测试新增)',
        'awards_new': 'awards(测试物化)',
        'student_winners_new': 'award_student_winners(测试关联)',
        'supervisors_new': 'award_supervisors(测试关联)',
        'audit_new': 'achievement_audit_log(测试留痕)',
        'patents_new': 'patents(测试残留)',
        'software_new': 'software_copyrights(测试残留)',
        'innovation_new': 'innovation_projects(测试残留)',
        'other_new': 'other_files(测试残留)',
        'users_new': 'users(测试创建账号,不含三真实账号)',
    }
    print("=== 待删清单统计 ===")
    for key, n in stats:
        print(f"  {zh.get(key, key)}: {n}")
    if not args.apply:
        print("\n[预览模式] 加 --apply 执行清理(将先 pg_dump 备份)")
        return

    # 1. 备份
    import os
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = rf"{BACKUP_DIR}\awardie_dev-pre-cleanup-{stamp}.sql"
    r = subprocess.run([DUMP, "-p", "5433", "-U", "postgres", "-d", "awardie_dev",
                        "-f", backup], capture_output=True, text=True)
    if r.returncode != 0:
        print("备份失败:", r.stderr[:300])
        sys.exit(1)
    print(f"[备份] {backup}")

    # 2. 清理(顺序:关联表→主表,避免 FK 残留)
    four_deletes = "".join(
        "\n    DELETE FROM " + tbl + " WHERE" + four_where[tbl] + ";"
        for tbl, _col, _k in four)
    cleanup = f"""
    DELETE FROM award_student_winners WHERE award_id IN (SELECT id FROM awards WHERE{tagged_where_awards});
    DELETE FROM award_supervisors WHERE award_id IN (SELECT id FROM awards WHERE{tagged_where_awards});
    DELETE FROM award_teacher_winners WHERE award_id IN (SELECT id FROM awards WHERE{tagged_where_awards});
    DELETE FROM achievement_audit_log WHERE created_at > '{CUTOFF}';
    DELETE FROM pending_achievements WHERE{tagged_where_pending};
    DELETE FROM awards WHERE{tagged_where_awards};{four_deletes}
    DELETE FROM users WHERE id > (SELECT COALESCE(MAX(id), 0) FROM users WHERE created_at < '2026-08-29')
      AND login_code NOT IN ('admin', '212306413', '02110606');
    """
    for stmt in [s.strip() for s in cleanup.split(";") if s.strip()]:
        q(stmt)
    print("[清理] 执行完成")

    # 3. 前后对照
    after = rows("""
        SELECT 'pending_achievements', COUNT(*) FROM pending_achievements
        UNION ALL SELECT 'awards', COUNT(*) FROM awards
        UNION ALL SELECT 'users', COUNT(*) FROM users
    """)
    print("=== 清理后计数 ===")
    for name, n in after:
        print(f"  {name}: {n}")
    print("[核对] awards 应回到迁移基线口径(197);pending 应仅剩迁移行")


if __name__ == "__main__":
    main()
