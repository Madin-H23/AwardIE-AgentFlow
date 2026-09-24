"""批3 dev 端到端验收:登录 → 建竞赛 → 重名拒绝 → 引用拒绝 → 逻辑删除引用后放行 → 清理。

纪律:Windows 控制台 curl 传中文会 GBK 变形导致 JSON 解析失败(项目已知坑),
中文表单一律走 venv python requests。
"""
import json
import os
import sys

import pymysql
import requests

BASE = "http://127.0.0.1:48080/admin-api"
TENANT = {"tenant-id": "1"}
PW = os.environ["AWARDIE_MYSQL_PASSWORD"]


def main() -> int:
    s = requests.Session()
    r = s.post(f"{BASE}/system/auth/login", json={"username": "admin", "password": "Mayy123"},
                headers=TENANT, timeout=10).json()
    token = r["data"]["accessToken"]
    H = {**TENANT, "Authorization": f"Bearer {token}"}
    ok = True

    def step(name, body, expect):
        nonlocal ok
        good = body.get("code") == expect
        ok = ok and good
        print(f"[{'PASS' if good else 'FAIL'}] {name}: code={body.get('code')} msg={body.get('msg')}")
        return body

    # 1. 读取 ETL 数据
    p = s.get(f"{BASE}/business/competitions/page", params={"pageNo": 1, "pageSize": 3}, headers=H, timeout=10).json()
    print(f"[INFO] 竞赛总数={p['data']['total']}(ETL 期望 218)")
    l = s.get(f"{BASE}/business/laboratories/page", params={"pageNo": 1, "pageSize": 10}, headers=H, timeout=10).json()
    print(f"[INFO] 实验室总数={l['data']['total']}(ETL 期望 5)")

    # 2. 新建竞赛
    name = "批3验收-临时竞赛"
    c = step("新建竞赛", s.post(f"{BASE}/business/competitions/create", json={
        "competitionName": name, "organizer": "验收组", "competitionTime": "4-10月",
        "gradeCategory": "本科组", "whiteList": True, "watchList": False}, headers=H, timeout=10).json(), 0)
    cid = c["data"]

    # 3. 重名拒绝
    step("重名拒绝", s.post(f"{BASE}/business/competitions/create", json={
        "competitionName": name, "whiteList": False, "watchList": False}, headers=H, timeout=10).json(), 1003001001)

    # 4. 引用拒绝:临时建 awardie_awards 引用该竞赛
    my = pymysql.connect(host="127.0.0.1", port=3307, user="awardie_v3", password=PW, database="awardie_v3")
    cur = my.cursor()
    cur.execute("DROP TABLE IF EXISTS awardie_awards")
    cur.execute("CREATE TABLE awardie_awards (id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                "competition_id BIGINT NULL, laboratory_id BIGINT NULL, "
                "deleted BIT(1) NOT NULL DEFAULT b'0')")
    cur.execute("INSERT INTO awardie_awards (competition_id, deleted) VALUES (%s, b'0')", (cid,))
    my.commit()
    step("被引用删除拒绝", s.delete(f"{BASE}/business/competitions/delete", params={"id": cid},
                                   headers=H, timeout=10).json(), 1003001002)

    # 5. 引用行逻辑删除后放行
    cur.execute("UPDATE awardie_awards SET deleted = b'1'")
    my.commit()
    step("引用已删后放行", s.delete(f"{BASE}/business/competitions/delete", params={"id": cid},
                                  headers=H, timeout=10).json(), 0)

    # 6. 清理探针表
    cur.execute("DROP TABLE IF EXISTS awardie_awards")
    my.commit()
    cur.execute("SELECT COUNT(*) FROM awardie_competitions")
    print(f"[INFO] 清理后竞赛总数={cur.fetchone()[0]}(期望 218,临时行已逻辑删除故查不到)")
    my.close()

    print("[result] " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
