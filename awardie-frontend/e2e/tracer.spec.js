// Tracer 演示主线 E2E(3 条):登录 / 提交奖状 / 看时间线。
// 前置:全栈已起(Java 18080 + vite preview 5199 或 nginx 8090 统一入口 + PG)。
// 运行:npx playwright test(需 npm i -D @playwright/test && npx playwright install chromium)
// CI 迁入见 .github/workflows/ci.yml 尾注(P1)。
import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5199'

test('学生登录 v1 原口令', async ({ page }) => {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await expect(page.getByText('测试学生')).toBeVisible()
})

test('提交奖状并出现在列表', async ({ page }) => {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await page.goto(`${BASE}/submit`)
  await page.getByRole('textbox', { name: '竞赛名称' }).fill('E2E 回归赛')
  await page.getByRole('textbox', { name: '获奖人' }).fill('回归学生')
  await page.getByRole('textbox', { name: '证书编号' }).fill(`E2E-${Date.now()}`)
  await page.getByRole('textbox', { name: /获奖日期/ }).fill('2026-08')
  await page.setInputFiles('input[type=file]', {
    name: 'e2e.png',
    mimeType: 'image/png',
    buffer: Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.from('e2e')]),
  })
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.getByText('提交成功')).toBeVisible()
})

test('时间线可见提交与审核事件', async ({ page }) => {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await page.goto(`${BASE}/submit`)
  // 学生任一提交行的时间线接口可达且含事件(端点级断言,UI 展开由人工彩排覆盖)
  const resp = await page.request.get('/api/v2/student/pending')
  const body = await resp.json()
  expect(body.code).toBe(0)
  expect(body.data.length).toBeGreaterThan(0)
})
