// tracer E2E 配置(#16):前置全栈已起(Java 18080 + vite preview 5199)
export default {
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5199',
    screenshot: 'only-on-failure',
  },
  workers: 1, // 提交有 sha256 去重断言,串行避免跨 worker 干扰
}
