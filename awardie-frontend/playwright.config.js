// tracer E2E 配置(#16):前置全栈已起(Java 18080 + vite preview 5199)
export default {
  testDir: './e2e',
  timeout: 60_000,
  // E2E 结束自动清理测试写入开发库的数据(Fix-A 数据治理;CI 无 python/psql 时跳过)
  globalTeardown: './e2e/global-teardown.js',
  // CI 上 vite 依赖 optimize 偶发中途 reload 打断 goto(ERR_ABORTED),重试一次
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://localhost:5199',
    screenshot: 'only-on-failure',
  },
  workers: 1, // 提交有 sha256 去重断言,串行避免跨 worker 干扰
}
