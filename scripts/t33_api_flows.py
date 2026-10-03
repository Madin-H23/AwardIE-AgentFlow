# -*- coding: utf-8 -*-
"""批33:全业务流 API 级验证(直打 E2E 后端 48081,隔离库)。
六流:通过链/驳回链/撤回/导出/vault 编辑/批量导入(fake)。
用途:把后端行为钉死为已知,GUI 层(Playwright)失败时即可归因为前端交互。
用法:venv python scripts/t33_api_flows.py
"""
import json
import time

import requests

BASE = 'http://127.0.0.1:48081/admin-api'
TAG = 'API' + str(int(time.time()))[-6:]
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  [ok] {name}')
    else:
        fail += 1
        print(f'  [FAIL] {name} {detail}')


def login(username, password):
    r = s.post(BASE + '/system/auth/login', json={'username': username, 'password': password},
               headers={'tenant-id': '1'}, timeout=15)
    return {'tenant-id': '1', 'Authorization': 'Bearer ' + r.json()['data']['accessToken']}


def upload(path, filename, typ, data):
    files = {'file': (filename, path, 'image/png')}
    r = s.post(BASE + '/business/pending-achievements/submit', files=files,
               data={'achievementType': typ, 'data': json.dumps(data, ensure_ascii=False)},
               headers=H_STU, timeout=20)
    return r.json()


s = requests.Session()
s.trust_env = False
H_AD = login('admin', 'Mayy123')
H_TEA = login('02110606', 'P@ss301')
H_STU = login('212306413', 'P@ss301')
print('== 三角色登录 OK ==')

# ===== Flow A 通过链 =====
print(f'== Flow A {TAG} ==')
r = s.post(BASE + '/business/laboratories/create', json={'name': f'E2E实验室{TAG}', 'description': 'API流'},
           headers=H_AD, timeout=15)
check('建实验室', r.json()['code'] == 0, r.text[:100])
r = s.post(BASE + '/business/competitions/create', json={'competitionName': f'E2E竞赛{TAG}', 'whiteList': False, 'watchList': False},
           headers=H_AD, timeout=15)
check('建竞赛', r.json()['code'] == 0, r.text[:100])

PNG = b'\x89PNG\r\n\x1a\n' + TAG.encode()
body = upload(PNG, f'e2e-{TAG}.png', 'award',
              {'competition_name': f'E2E竞赛{TAG}', 'award_level': '一等奖',
               'winner_name': '陈品天', 'supervisor_name': '黄巧云', 'date': '2025-05-01'})
check('学生提交', body['code'] == 0, str(body)[:150])
aid = body['data']['id']

r = s.get(BASE + '/business/pending-achievements/teacher-pending-list',
          params={'status': 'pending'}, headers=H_TEA, timeout=15)
rows = r.json()['data']
mine = [x for x in rows if x['id'] == aid]
check('教师队列含该行(姓名过滤)', len(mine) == 1, f'队列 {len(rows)} 行')

r = s.post(BASE + f'/business/pending-achievements/{aid}/review',
           json={'action': 'approve', 'comment': 'API 通过'}, headers=H_TEA, timeout=20)
check('教师通过', r.json()['code'] == 0, r.text[:150])

r = s.get(BASE + '/business/vault/award', params={'pageNo': 1, 'pageSize': 10, 'keyword': f'E2E竞赛{TAG}'},
          headers=H_AD, timeout=15)
check('成果库物化行', (r.json().get('data') or {}).get('total', 0) >= 1, r.text[:150])

r = s.get(BASE + '/business/pending-achievements/download', params={'id': aid}, headers=H_STU, timeout=15)
check('学生证书下载(真实文件)', r.headers.get('content-type', '').startswith('image/'), r.text[:80])

# ===== Flow B 驳回链 =====
print(f'== Flow B {TAG}b ==')
body = upload(PNG, f'e2e-{TAG}b.png', 'patent',
              {'patent_name': f'E2E专利{TAG}b', 'patent_type': '发明专利'})
check('学生提交专利', body['code'] == 0, str(body)[:150])
bid = body['data']['id']
r = s.post(BASE + f'/business/pending-achievements/{bid}/review',
           json={'action': 'reject', 'comment': f'E2E驳回原因{TAG}b'}, headers=H_AD, timeout=20)
check('admin 驳回', r.json()['code'] == 0, r.text[:150])
r = s.get(BASE + '/business/pending-achievements/my-page',
          params={'pageNo': 1, 'pageSize': 20}, headers=H_STU, timeout=15)
row = [x for x in r.json()['data']['list'] if x['id'] == bid][0]
check('学生看到驳回态', row['status'] == 'rejected', row['status'])
check('驳回原因回显', f'E2E驳回原因{TAG}b' in (row.get('reviewComment') or ''), str(row)[:120])

# ===== Flow C 撤回 =====
print(f'== Flow C {TAG}c ==')
body = upload(PNG, f'e2e-{TAG}c.png', 'software',
              {'software_name': f'E2E软著{TAG}c'})
check('学生提交软著', body['code'] == 0, str(body)[:150])
cid = body['data']['id']
r = s.delete(BASE + '/business/pending-achievements/withdraw', params={'id': cid}, headers=H_STU, timeout=15)
check('撤回', r.json()['code'] == 0, r.text[:100])

# ===== Flow D 导出 =====
print(f'== Flow D {TAG} ==')
r = s.get(BASE + '/business/export/competition-summary.csv', headers=H_AD, timeout=30)
check('竞赛年度汇总导出', len(r.content) > 50, f'{len(r.content)} bytes')
r2 = s.get(BASE + '/business/export/student-affairs.csv', headers=H_AD, timeout=30)
check('学生获奖明细导出', len(r2.content) > 50, f'{len(r2.content)} bytes')

# ===== Flow E vault 编辑 =====
print(f'== Flow E {TAG} ==')
r = s.get(BASE + '/business/vault/award', params={'pageNo': 1, 'pageSize': 10, 'keyword': f'E2E竞赛{TAG}'},
          headers=H_AD, timeout=15)
vrow = r.json()['data']['list'][0]
r = s.post(BASE + f'/business/vault/award/{vrow["id"]}/update',
           json={'winner_name': f'E2E改名人{TAG}'},
           headers=H_AD, timeout=15)
check('vault 行编辑', r.json()['code'] == 0, r.text[:150])

# ===== Flow F 批量导入(fake parse) =====
print(f'== Flow F {TAG} ==')
parsed_ok = 0
for i in (1, 2):
    r = s.post(BASE + '/business/pending-achievements/parse',
               files={'file': (f'e2e-{TAG}f{i}.png', PNG, 'image/png')}, headers=H_AD, timeout=30)
    if r.json().get('code') == 0:
        parsed_ok += 1
check('批量 AI 识别(fake,逐张 parse)', parsed_ok == 2)

print(f'\n== 结果: {ok} ok / {fail} fail ==')
