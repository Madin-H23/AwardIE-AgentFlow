#!/usr/bin/env bash
# 批33:全功能业务流测试编排(E2E 隔离沙箱)。
# 流程:重建 awardie_v3_e2e(七链+账号克隆) → 后端 48081(双源覆盖+redis 3)
#   → 前端 81(VITE_BASE_URL 指 48081) → Playwright 业务流 → teardown。
# 前置:真实后端 48080 可在跑(与本编排互不干扰);MySQL 3307、Redis 6379 在。
# 用法:e2e/run-flows.sh            (AWARDIE_MYSQL_ROOT_PASSWORD 从 Windows 用户环境取)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../" && pwd)"
FE="$ROOT/awardie-v3/yudao-ui/yudao-ui-admin-vue3"
export AWARDIE_MYSQL_ROOT_PASSWORD="${AWARDIE_MYSQL_ROOT_PASSWORD:-$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AWARDIE_MYSQL_PASSWORD','User')" | tr -d '\r')}"
E2E_PW="e2e-$(date +%s)"

cleanup() {
  echo "== teardown =="
  powershell -NoProfile -Command "
foreach (\$p in 48081, 81) {
  \$c = Get-NetTCPConnection -LocalPort \$p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
  if (\$c) { Stop-Process -Id \$c -Force -ErrorAction SilentlyContinue }
}"
}
trap cleanup EXIT

echo "== 1/5 重建 E2E 库 =="
/d/venvs/awardie/Scripts/python.exe "$ROOT/scripts/v3_e2e_env.py" --apply --e2e-password "$E2E_PW" || exit 1

echo "== 2/5 起 E2E 后端 48081 =="
powershell -NoProfile -Command "
\$c = Get-NetTCPConnection -LocalPort 48081 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if (\$c) { Stop-Process -Id \$c -Force -ErrorAction SilentlyContinue }
\$env:SERVER_PORT = '48081'
\$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_URL = 'jdbc:mysql://127.0.0.1:3307/awardie_v3_e2e?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true'
\$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_USERNAME = 'awardie_e2e_ro'
\$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_SLAVE_URL = 'jdbc:mysql://127.0.0.1:3307/awardie_v3_e2e?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&rewriteBatchedStatements=true&nullCatalogMeansCurrent=true'
\$env:SPRING_DATASOURCE_DYNAMIC_DATASOURCE_SLAVE_USERNAME = 'awardie_e2e_ro'
\$env:AWARDIE_MYSQL_PASSWORD = '$E2E_PW'
\$env:SPRING_DATA_REDIS_DATABASE = '3'
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','cd /d D:\Develop\AI 应用开发\AI应用开发项目\AwardIE-AgentFlow\awardie-v3 && mvn -pl yudao-server spring-boot:run > NUL 2>&1' -WindowStyle Hidden
Write-Output 'backend starting'
"
UP=0
for i in $(seq 1 40); do
  sleep 5
  if netstat -ano | grep ":48081 " | grep -q LISTENING; then UP=1; echo "48081 UP after ~$((i*5))s"; break; fi
done
[ "$UP" = "1" ] || { echo "后端 48081 未起"; exit 1; }

echo "== 3/5 构建并起 E2E 前端 81(直连 48081) =="
# 走 build:local + vite preview 而非 pnpm dev:vite dev 的按需依赖预构建会在运行中强制
# 整页 reload,打断 Playwright 定位(实测 11 轮中 A/B 流偶发登录白屏;preview 无此机制)
cd "$FE"
VITE_BASE_URL='http://127.0.0.1:48081' pnpm build:local > NUL 2>&1 || { echo "build:local 失败"; exit 1; }
powershell -NoProfile -Command "
\$c = Get-NetTCPConnection -LocalPort 81 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if (\$c) { Stop-Process -Id \$c -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','cd /d D:\Develop\AI 应用开发\AI应用开发项目\AwardIE-AgentFlow\awardie-v3\yudao-ui\yudao-ui-admin-vue3 && npx vite preview --port 81 --host 127.0.0.1 > NUL 2>&1' -WindowStyle Hidden
Write-Output 'preview starting'
"
UP=0
for i in $(seq 1 30); do
  sleep 4
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" --max-time 4 "http://127.0.0.1:81" 2>/dev/null)
  if [ "$code" = "200" ]; then UP=1; echo "81 UP after ~$((i*4))s"; break; fi
done
[ "$UP" = "1" ] || { echo "前端 81 未起"; exit 1; }

echo "== 4/5 登录冒烟(隔离库链路) =="
/d/venvs/awardie/Scripts/python.exe -c "
import requests
s = requests.Session(); s.trust_env = False
r = s.post('http://127.0.0.1:48081/admin-api/system/auth/login', json={'username':'admin','password':'Mayy123'}, headers={'tenant-id':'1'}, timeout=15)
print('隔离库登录:', 'OK' if r.json()['code']==0 else r.text[:120])
" || exit 1

echo "== 5/5 Playwright 业务流(清 test-results 避免跨轮残留) =="
rm -rf test-results
cd "$FE"
E2E_FLOWS=on E2E_FLOWS_BASE="http://127.0.0.1:81" npx playwright test e2e/flows.spec.ts
RC=$?
echo "== 业务流退出码 $RC(实例保留供检查,手动关或下次编排清理) =="
trap - EXIT
exit $RC
