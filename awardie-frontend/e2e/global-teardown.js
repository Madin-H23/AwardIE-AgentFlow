// E2E 结束后自动清理测试写入开发库的数据(Fix-A 数据治理)。
// 原理:调用 scripts/v2_cleanup_testdata.py --apply(幂等:仅删迁移基线之后的测试行,
// 先 pg_dump 备份再清理)。CI 上 psql/python 路径不可用时静默跳过(CI 库每轮新建,无累积)。
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default async function () {
  const script = path.resolve(__dirname, '../../scripts/v2_cleanup_testdata.py')
  if (!fs.existsSync(script)) {
    console.warn('[e2e-teardown] 清理脚本不存在,跳过:', script)
    return
  }
  for (const py of ['python', 'python3']) {
    const r = spawnSync(py, [script, '--apply', '--tagged'], {
      encoding: 'utf8', timeout: 120_000, // 防 psql 挂起阻塞 teardown(OCR low 修复)
    })
    if (r.status === 0) {
      console.log('[e2e-teardown] 测试数据已清理(v2_cleanup_testdata --apply)')
      return
    }
  }
  console.warn('[e2e-teardown] 自动清理未执行(本机无可用 python/psql),可手动运行 scripts/v2_cleanup_testdata.py --apply')
}
