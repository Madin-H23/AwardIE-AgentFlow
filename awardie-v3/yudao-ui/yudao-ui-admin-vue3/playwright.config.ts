import { defineConfig } from '@playwright/test'

// UX-1 批28 D-13:v3 前端 E2E 从零起步(v2 的 playwright.config.js 为模板)。
// 前置:后端 48080 + 前端 dev server 均已起(本地常规形态);冒烟只读,不写业务库。
// 端口默认 80(v3 dev server);v2 的 5199 只听 IPv6 的坑与本机无关,baseURL 走 IPv4 环回。
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  // CI 上 vite 依赖 optimize 偶发中途 reload 打断 goto(v2 同款教训),重试一次
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.E2E_BASE || 'http://127.0.0.1:80',
    // 默认只留失败截图;取证时 E2E_SCREENSHOT=on 全留(批28 惯例:证据随批入库)
    screenshot: process.env.E2E_SCREENSHOT === 'on' ? 'on' : 'only-on-failure',
  },
  workers: 1, // 登录态与菜单缓存有服务端状态,串行避免跨 worker 干扰
})
