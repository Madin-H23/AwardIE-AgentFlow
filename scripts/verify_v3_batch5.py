"""批5 dev 端到端验收:提交 → 教师审(AI 建议/通过)→ 物化 → 时间线 → 驳回必填原因。

纪律:Windows 控制台 curl 传中文会 GBK 变形(项目已知坑),中文表单一律走 venv python requests。
口令走环境变量,不入库。
"""
import json
import os
import sys

import pymysql
import requests

BASE = "http://127.0.0.1:48080/admin-api"
TENANT = {"tenant-id": "1"}
PW = os.environ["AWARDIE_MYSQL_PASSWORD"]
JPEG = b"\xff\xd8\xff\xe0\x31\x32\x33\x44"
AWARD_JSON = json.dumps({"competition_name": "批5验收-自动建竞赛", "award_level": "一等奖",
                         "winner_name": "王五", "date": "2024-07-01"}, ensure_ascii=False)


def main() -> int:
    s = requests.Session()
    r = s.post(f"{BASE}/system/auth/login", json={"username": "admin", "password": "Mayy123"},
               headers=TENANT, timeout=10).json()
    H = {**TENANT, "Authorization": f"Bearer {r['data']['accessToken']}"}
    ok = True

    def step(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")

    # 1. 提交成果(竞赛名故意用不存在的,验证 approve 时自动建)
    sub = s.post(f"{BASE}/business/pending-achievements/submit",
                 files={"file": ("c.jpg", JPEG, "image/jpeg")},
                 data={"achievementType": "award", "data": AWARD_JSON}, headers=H, timeout=15).json()
    step("提交成果", sub.get("code") == 0, f"id={sub.get('data', {}).get('id')}")
    pid = sub["data"]["id"]

    # 2. AI 建议(fake 模式)
    sug = s.get(f"{BASE}/business/pending-achievements/{pid}/ai-suggest", headers=H, timeout=10).json()
    step("AI 建议", sug.get("code") == 0 and sug["data"]["decision"] == "pass"
         and "AI 建议仅辅助参考" in sug["data"]["suggestion"], sug["data"]["decision"])

    # 3. 教师待审列表(join 提交者姓名)
    lst = s.get(f"{BASE}/business/pending-achievements/teacher-pending-list",
                params={"status": "pending"}, headers=H, timeout=10).json()
    step("待审列表", lst.get("code") == 0 and len(lst.get("data", [])) >= 1
         and "submitterName" in lst["data"][0], f"count={len(lst.get('data', []))}")

    # 4. 驳回必填原因
    rej0 = s.post(f"{BASE}/business/pending-achievements/{pid}/review", headers=H, timeout=10,
                  json={"action": "reject", "comment": ""}).json()
    step("驳回空原因拒绝", rej0.get("code") == 1003004001)

    # 5. 通过 → 物化 + 竞赛自动建
    appr = s.post(f"{BASE}/business/pending-achievements/{pid}/review", headers=H, timeout=15,
                  json={"action": "approve", "comment": "批5验收通过"}).json()
    step("审核通过", appr.get("code") == 0 and appr["data"]["status"] == "archived")

    my = pymysql.connect(host="127.0.0.1", port=3307, user="awardie_v3", password=PW, database="awardie_v3")
    cur = my.cursor()
    cur.execute("SELECT COUNT(*) FROM awardie_awards WHERE deleted=b'0'")
    awards = cur.fetchone()[0]
    step("物化入 awards", awards >= 1, f"rows={awards}")
    cur.execute("SELECT is_auto_added FROM awardie_competitions WHERE competition_name=%s",
                ("批5验收-自动建竞赛",))
    row = cur.fetchone()
    # MySQL BIT 列 pymysql 返回 bytes(b''=true),按真值判定
    step("竞赛自动建", row is not None and bool(row[0]), f"is_auto_added={row[0] if row else '缺失'}")
    cur.execute("SELECT action_type FROM awardie_achievement_audit_log WHERE achievement_id=%s ORDER BY id",
                (pid,))
    actions = [r[0] for r in cur.fetchall()]
    step("审计留痕(1/6/8)", actions == [1, 6, 8], f"action_types={actions}")

    # 6. 时间线
    tl = s.get(f"{BASE}/business/pending-achievements/{pid}/timeline", headers=H, timeout=10).json()
    step("时间线", tl.get("code") == 0 and len(tl.get("data", [])) == 3, f"entries={len(tl.get('data', []))}")

    # 7. 幂等:重置状态再审一次,成果表不应重复
    cur.execute("UPDATE awardie_pending_achievements SET status='pending' WHERE id=%s", (pid,))
    my.commit()
    again = s.post(f"{BASE}/business/pending-achievements/{pid}/review", headers=H, timeout=15,
                   json={"action": "approve", "comment": "重复审批"}).json()
    cur.execute("SELECT COUNT(*) FROM awardie_awards WHERE deleted=b'0'")
    after = cur.fetchone()[0]
    step("幂等(不重复物化)", again.get("code") == 0 and after == awards, f"awards={after}")

    my.close()
    print("[result] " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
