// UX-1 批28 冒烟(只读,不写业务库):
// 1) 五个接入 PageHeader 的列表页逐页可达且页头渲染
// 2) TableSkeleton 在待审管理首载真实出现(拦截接口延迟,确定性非竞速)
// 3) 双壳路由过渡接线后跨页跳转正常(admin 壳 + 学生门户壳)
// 账号为本地存量约定(v1 起同款,README 同款)。
import { expect, test, type Page } from '@playwright/test'

const ADMIN_PAGES: Array<[string, string]> = [
  ['/business/pending-achievements', '待审管理'],
  ['/business/logs', '审计日志'],
  ['/business/stats', '统计分析'],
  ['/business/competitions', '竞赛管理'],
  ['/business/vault', '成果库'],
]

async function login(page: Page, username: string, password: string) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  // 登录页同屏还有演示/找回表单,同名占位符的密码框有 3 个,取 DOM 首个(即登录表单本体)
  await page.getByPlaceholder('请输入密码').first().fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).first().click()
  await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 20_000 })
}

test('admin 五页 PageHeader 渲染 + 跨页跳转(路由过渡接线后)', async ({ page }) => {
  await login(page, 'admin', 'Mayy123')
  for (const [path, title] of ADMIN_PAGES) {
    await page.goto(path)
    await expect(page.locator('.page-header .ph-title')).toHaveText(title)
  }
  // 路由过渡改写 AppView 后,keep-alive 缓存页往返不得白屏/丢渲染
  await page.goto(ADMIN_PAGES[0][0])
  await expect(page.locator('.page-header .ph-title')).toBeVisible()
})

test('待审管理首载出 TableSkeleton(接口延迟注入,确定性)', async ({ page }) => {
  await login(page, 'admin', 'Mayy123')
  // admin 待审列表走 teacher-pending-list(批9 教训:my-page 按当前用户过滤,admin 必须用教师口径)
  await page.route('**/admin-api/business/pending-achievements/**', async (route) => {
    await new Promise((r) => setTimeout(r, 1500))
    await route.continue()
  })
  await page.goto('/business/pending-achievements')
  await expect(page.locator('.table-skeleton')).toBeVisible({ timeout: 5_000 })
  await expect(page.locator('.table-skeleton')).toBeHidden({ timeout: 15_000 })
  await expect(page.locator('.el-table')).toBeVisible()
})

test('学生门户三页可达(门户壳过渡接线后)', async ({ page }) => {
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/submit')
  await expect(page.locator('.portal-nav')).toBeVisible()
  await expect(page.locator('.portal-nav__item', { hasText: '我的证书' })).toBeVisible()
  // tab 点击跳转(过渡路径)到证书页
  await page.locator('.portal-nav__item', { hasText: '我的证书' }).click()
  await expect(page).toHaveURL(/\/portal\/certificates/)
  await expect(page.locator('.portal-main')).not.toBeEmpty()
})

test('暗色主题三代表页渲染 + 无横向溢出(批30 双态全覆盖的常态化回归)', async ({ page }) => {
  await login(page, 'admin', 'Mayy123')
  for (const path of ['/business/stats', '/business/vault', '/business/competitions']) {
    await page.goto(path)
    await page.evaluate(() => document.documentElement.classList.add('dark'))
    await page.waitForTimeout(300)
    // 页头在暗色下仍渲染(新 token 组 --medal-*/--ribbon-* 全部走 .dark 分支)
    await expect(page.locator('.page-header .ph-title')).toBeVisible()
    const over = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    )
    expect(over, `${path} 暗色横向溢出 ${over}px`).toBeLessThanOrEqual(0)
  }
})

test('品牌清理:登录页与业务页文本零框架名称(批32 常态化回归)', async ({ page }) => {
  // 登录页(未登录态,含租户框预填值)。dev 模式 load 事件早于异步 chunk 挂载,
  // 须 networkidle(与 login() helper 一致),否则表单未挂载即断言
  await page.goto('/login', { waitUntil: 'networkidle' })
  // 注意:页面上有两个 .login-form(登录表单+隐藏的忘记密码表单,同 class 名),
  // 类选择器会撞 strict 多匹配——用语义占位符断言真实登录表单
  await expect(page.getByPlaceholder('请输入用户名')).toBeVisible()
  expect(await page.locator('body').innerText()).not.toContain('芋道')
  // 业务页(登录态,含侧栏/页头/footer)
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/competitions')
  await expect(page.locator('.page-header .ph-title')).toHaveText('竞赛管理')
  expect(await page.locator('body').innerText()).not.toContain('芋道')
})
