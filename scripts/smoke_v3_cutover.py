"""临时冒烟脚本:v3 切流后三角色登录 + 关键端点抽查。用完即删(agent 自建临时产物)。

仅做只读请求(login + 列表查询),不写任何业务数据。
"""
import json
import sys

import requests

BASE = 'http://127.0.0.1:48080'
HEADERS = {'tenant-id': '1', 'Content-Type': 'application/json'}
# 本机 3067 系统代理会把 127.0.0.1 吞掉,禁用环境代理直连
S = requests.Session()
S.trust_env = False

ACCOUNTS = [('admin', 'Mayy123'), ('02110606', 'P@ss301'), ('212306413', 'P@ss301')]


def login(username, password):
    r = S.post(f'{BASE}/admin-api/system/auth/login',
               headers=HEADERS,
               json={'username': username, 'password': password},
               timeout=15)
    body = r.json()
    return body.get('code') == 0, body


def get(path, token):
    h = dict(HEADERS)
    h['Authorization'] = f'Bearer {token}'
    r = S.get(f'{BASE}{path}', headers=h, timeout=15)
    try:
        body = r.json()
    except ValueError:
        return r.status_code, None
    return body.get('code'), body


def main():
    results = []
    for username, password in ACCOUNTS:
        ok, body = login(username, password)
        token = (body.get('data') or {}).get('accessToken') if ok else None
        name = (body.get('data') or {}).get('userId') if ok else body.get('msg')
        results.append((username, '登录OK' if ok else f'登录FAIL({body.get("msg")})', token))
        print(f'[login] {username:<12} {"OK" if ok else "FAIL"}  userId={name}')
        if not ok:
            continue

        # 角色化抽查:只发只读列表请求,看 code==0 且有数据
        checks = [
            ('/admin-api/system/auth/get-permission-info', '权限信息'),
        ]
        if username == 'admin':
            checks.append(('/admin-api/business/competitions/page?pageNo=1&pageSize=5', '竞赛分页'))
            checks.append(('/admin-api/business/vault/award?pageNo=1&pageSize=5', '成果库-获奖'))
            checks.append(('/admin-api/business/pending-achievements/teacher-pending-list'
                           '?pageNo=1&pageSize=5', '待审队列'))
            checks.append(('/admin-api/business/stats/overview', '统计总览'))
        elif username == '02110606':
            checks.append(('/admin-api/business/vault/award?pageNo=1&pageSize=5', '成果库-获奖(教师)'))
            checks.append(('/admin-api/business/pending-achievements/teacher-pending-list'
                           '?pageNo=1&pageSize=5', '待审队列(教师)'))
        elif username == '212306413':
            checks.append(('/admin-api/business/pending-achievements/my-page?pageNo=1&pageSize=5',
                           '我的提交(学生)'))
        results_token = token
        for path, label in checks:
            code, body = get(path, results_token)
            total = None
            if isinstance(body, dict):
                data = body.get('data')
                if isinstance(data, dict) and 'total' in data:
                    total = data.get('total')
                elif isinstance(data, dict) and 'list' in data:
                    total = len(data.get('list') or [])
            print(f'  [{label}] code={code} total={total}')
            results.append((username, f'{label} code={code} total={total}', None))

    fails = [r for r in results if 'FAIL' in str(r[1])]
    print()
    print(f'冒烟结论: {"PASS" if not fails else "FAIL"}  (失败 {len(fails)} 项)')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
