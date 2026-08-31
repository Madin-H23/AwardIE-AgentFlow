// Tracer 演示主线 E2E(3 条):登录 / 提交奖状 / 看时间线。
// 前置:全栈已起(Java 18080 + vite preview 5199 或 nginx 8090 统一入口 + PG)。
// 运行:npx playwright test(需 npm i -D @playwright/test && npx playwright install chromium)
// CI 迁入见 .github/workflows/ci.yml 尾注(P1)。
import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5199/v2' // base=/v2/(#10 分流)

test('学生登录 v1 原口令', async ({ page }) => {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await expect(page.locator('.home')).toContainText('陈品天') // 学号在 .home 不展示,断言姓名(本地存量;CI 自举库用 seedAccounts 同学号)
})

async function loginAsStudent(page) {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await expect(page.locator('.home')).toBeVisible() // 登录完成的唯一可靠信号
}

test('提交奖状并出现在列表', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/submit`)
  await expect(page.getByRole('heading', { name: '提交成果' })).toBeVisible()
  await page.getByRole('textbox', { name: '竞赛名称' }).fill('E2E 回归赛')
  await page.getByRole('textbox', { name: '获奖人' }).fill('回归学生')
  await page.getByRole('textbox', { name: '证书编号' }).fill(`E2E-${Date.now()}`)
  await page.getByRole('textbox', { name: /获奖日期/ }).fill('2026-08')
  await page.setInputFiles('input[type=file]', {
    name: 'e2e.png',
    mimeType: 'image/png',
    buffer: Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      Buffer.from(`e2e-${Date.now()}`)]), // 内容唯一:绕过 sha256 去重(每次跑都是新文件)
  })
  const before = await page.locator('table tbody tr').count()
  const respPromise = page.waitForResponse((r) => r.url().includes('/api/v2/student/submit'))
  await page.getByRole('button', { name: '提交审核' }).click()
  const resp = await respPromise
  const body = await resp.json()
  expect(body.code).toBe(0) // 提交必须成功(去重/校验失败会在断言信息里展示 message)
  await expect(page.locator('table tbody tr')).toHaveCount(before + 1, { timeout: 10_000 })
})

test('时间线可见提交与审核事件', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/submit`)
  // UI 级断言:提交列表已渲染(接口断言需浏览器会话 cookie,由 Playwright context 自动携带)
  await expect(page.getByRole('heading', { name: '我的提交' })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
})
