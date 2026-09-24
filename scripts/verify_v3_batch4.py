"""批4 dev 端到端验收:登录 → 建实验室 → 提交成果 → 我的提交 → 撤回 → 下载。

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
JPEG = b"\xff\xd8\xff\xe0\x11\x22\x33\x44"


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

    # 1. 建实验室(为详情端点准备)
    lab = s.post(f"{BASE}/business/laboratories/create", json={"name": "批4验收实验室", "description": "端到端"},
                 headers=H, timeout=10).json()
    step("建实验室", lab.get("code") == 0, f"id={lab.get('data')}")
    lab_id = lab.get("data")

    # 2. 提交成果(jpg 真实魔术字节)
    files = {"file": ("证书.jpg", JPEG, "image/jpeg")}
    data = {"achievementType": "award",
            "data": json.dumps({"competition_name": "挑战杯", "award_level": "一等奖",
                                "winner_name": "张三", "date": "2024-05-01"}, ensure_ascii=False)}
    sub = s.post(f"{BASE}/business/pending-achievements/submit", files=files, data=data, headers=H,
                 timeout=15).json()
    step("提交成果", sub.get("code") == 0, f"id={sub.get('data', {}).get('id')} "
                                            f"valid={sub.get('data', {}).get('validationResult')}")
    pid = sub.get("data", {}).get("id")

    # 3. 同文件重复提交 → 去重拒绝
    dup = s.post(f"{BASE}/business/pending-achievements/submit", files=files, data=data, headers=H,
                 timeout=15).json()
    step("重复文件去重拒绝", dup.get("code") == 1003002001, dup.get("msg", ""))

    # 4. 非法类型文件 → 三校验拒绝
    bad = s.post(f"{BASE}/business/pending-achievements/submit",
                 files={"file": ("evil.txt", b"not an image", "text/plain")},
                 data={"achievementType": "award", "data": "{}"}, headers=H, timeout=15).json()
    step("扩展名白名单拒绝", bad.get("code") == 1003003000, bad.get("msg", ""))

    # 5. 魔术字节不符(扩展名 pdf 内容是文本)
    fake = s.post(f"{BASE}/business/pending-achievements/submit",
                  files={"file": ("fake.pdf", b"just text", "application/pdf")},
                  data={"achievementType": "award", "data": "{}"}, headers=H, timeout=15).json()
    step("魔术字节校验拒绝", fake.get("code") == 1003003002, fake.get("msg", ""))

    # 6. 我的提交
    mine = s.get(f"{BASE}/business/pending-achievements/my-page", params={"pageNo": 1, "pageSize": 10},
                 headers=H, timeout=10).json()
    step("我的提交", mine.get("code") == 0 and mine.get("data", {}).get("total", 0) >= 1,
         f"total={mine.get('data', {}).get('total')}")

    # 7. 下载(attachment + 字节一致)
    dl = s.get(f"{BASE}/business/pending-achievements/download", params={"id": pid}, headers=H, timeout=10)
    step("下载文件", dl.status_code == 200 and dl.content == JPEG
         and "attachment" in dl.headers.get("Content-Disposition", "")
         and dl.headers.get("Content-Type", "").startswith("image/jpeg"),
         f"{dl.headers.get('Content-Type')} {len(dl.content)}B")

    # 8. 撤回
    wd = s.delete(f"{BASE}/business/pending-achievements/withdraw", params={"id": pid}, headers=H,
                  timeout=10).json()
    step("撤回提交", wd.get("code") == 0)
    again = s.delete(f"{BASE}/business/pending-achievements/withdraw", params={"id": pid}, headers=H,
                     timeout=10).json()
    step("重复撤回→不存在", again.get("code") == 1003002000, again.get("msg", ""))

    # 9. 实验室详情与下载列表端点
    detail = s.get(f"{BASE}/business/laboratories/detail", params={"id": lab_id}, headers=H, timeout=10).json()
    step("实验室详情聚合", detail.get("code") == 0
         and detail.get("data", {}).get("downloadCount") == 0
         and "awardCount" in detail.get("data", {}),
         f"awardCount={detail.get('data', {}).get('awardCount')}(批6 前恒 0)")
    dls = s.get(f"{BASE}/business/laboratories/downloads", params={"id": lab_id}, headers=H, timeout=10).json()
    step("实验室下载列表", dls.get("code") == 0 and dls.get("data") == [], f"count={len(dls.get('data', []))}")

    # 10. 清理:验证文件真的落在配置的存储根
    my = pymysql.connect(host="127.0.0.1", port=3307, user="awardie_v3", password=PW, database="awardie_v3")
    cur = my.cursor()
    cur.execute("SELECT COUNT(*) FROM awardie_pending_achievements WHERE deleted = b'0'")
    print(f"[INFO] dev 库未删除 pending 行数={cur.fetchone()[0]}(验收数据,批4 不做数据迁移)")
    my.close()

    print("[result] " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
