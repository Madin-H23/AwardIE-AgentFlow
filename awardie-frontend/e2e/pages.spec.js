// 全页面冒烟(#10 首页缺失事件的补防):每页断言核心渲染元素。
// 前置:全栈已起;账号为本地存量(admin)。
import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5199/v2'

async function loginAsAdmin(page) {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('admin')
  await page.getByTestId('login-password').fill('Mayy123')
  await page.getByTestId('login-submit').click()
  await expect(page.locator('.home')).toBeVisible()
}

test('首页展示业务入口与管理端入口', async ({ page }) => {
  await loginAsAdmin(page)
  await expect(page.locator('.home')).toContainText('业务入口')
  await expect(page.locator('.home')).toContainText('管理端(admin)')
  await expect(page.locator('.home').locator('a', { hasText: '数据看板' })).toBeVisible()
})

test('提交页含表单/我的提交/我的成果', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/submit`)
  await expect(page.getByRole('heading', { name: '提交成果' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的提交' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的成果(已入库)' })).toBeVisible()
})

test('时间线对话框展示事件', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/submit`)
  await expect(page.locator('table tbody tr').first()).toBeVisible()
  await page.locator('button', { hasText: '查看' }).first().click()
  await expect(page.locator('.el-dialog__title')).toContainText('时间线')
  // 事件或空态二选一可见(老测试行无留痕)
  await expect(page.locator('.el-timeline, .el-empty').first()).toBeVisible({ timeout: 10_000 })
})

test('教师审核台渲染(admin 视角)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/teacher/review`)
  await expect(page.getByRole('heading', { name: '待审列表' })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
})

test('个人资料按角色渲染字段', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/profile`)
  await expect(page.getByRole('heading', { name: /个人资料/ })).toBeVisible()
  await expect(page.getByTestId('profile-name')).toBeVisible()
})

test('admin 成果管理渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/awards`)
  await expect(page.getByRole('heading', { name: '成果管理' })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
})

test('admin 竞赛管理渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/competitions`)
  await expect(page.getByRole('heading', { name: '竞赛管理' })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
})

test('admin 看板渲染(ECharts)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/dashboard`)
  await expect(page.getByText('成果总数')).toBeVisible()
  await expect(page.locator('div[ref] canvas, .dash-page canvas').first()).toBeVisible({ timeout: 10_000 })
})

// #29 侧边栏补全批次:五新页冒烟
test('侧边栏对照 v1 全量菜单', async ({ page }) => {
  await loginAsAdmin(page)
  const sidebar = page.locator('.console-sidebar')
  for (const label of ['数据总览', '成果管理', '成果审核', '日志管理', 'AI 智能体协作', '成果/文件导入',
    '奖状模板管理', '竞赛管理', '实验室管理', '学生管理', '教师管理', '数据分析', '数据导出', '系统设置']) {
    await expect(sidebar.locator('.nav-link', { hasText: label }).first()).toBeVisible()
  }
})

test('日志管理双源渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/logs`)
  // CI 空库无留痕行:数据行或空态二选一(环境×数据无关)
  await expect(page.locator('.log-stream .log-line, .log-stream .empty-state').first()).toBeVisible({ timeout: 10_000 })
  await page.locator('.el-radio-button', { hasText: '系统事件' }).click()
  await expect(page.locator('.log-stream')).toBeVisible()
})

test('学生管理与教师管理渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/students`)
  await expect(page.getByRole('heading', { name: '学生管理' })).toBeVisible()
  await expect(page.locator('.el-table').locator('tbody tr').first()).toBeVisible({ timeout: 10_000 })
  await page.goto(`${BASE}/admin/teachers`)
  await expect(page.getByRole('heading', { name: '教师管理' })).toBeVisible()
})

test('实验室与奖状模板页渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/laboratories`)
  await expect(page.getByRole('heading', { name: '实验室管理' })).toBeVisible()
  await page.goto(`${BASE}/admin/templates`)
  await expect(page.getByRole('heading', { name: '奖状模板管理' })).toBeVisible()
  await expect(page.locator('.el-table').first()).toBeVisible()
})

test('未迁移菜单落占位页', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/logs`)
  await page.locator('.console-sidebar .nav-link', { hasText: '数据分析' }).click()
  await expect(page.getByRole('heading', { name: /迁移中/ })).toBeVisible()
})
