// 批33 全功能业务流测试(E2E 隔离沙箱 awardie_v3_e2e,写入不碰真实库)。
// 运行前置:e2e/run-flows.sh 编排(建库→后端 48081→前端 81→本文件)。
// 环境变量 E2E_FLOWS=on 才执行;E2E_FLOWS_BASE 指向隔离前端(默认 81)。
// 数据标记:全部业务数据带时间戳 TAG,隔离库每次重建,无需清理。
import { expect, test, type Page } from '@playwright/test'

const BASE = process.env.E2E_FLOWS_BASE || 'http://127.0.0.1:81'
test.use({ baseURL: BASE })
test.skip(process.env.E2E_FLOWS !== 'on', '业务流仅在 E2E 隔离环境运行(e2e/run-flows.sh 编排)')

// vite dev 依赖预构建会强制页面 reload,偶发打断定位(实测 9 轮中 2 次);
// 用例级重试一次兜住环境竞态——业务断言本身是确定性的
test.describe.configure({ retries: 1 })

const TAG = 'E2E' + String(Date.now()).slice(-6)
/** 唯一 PNG(时间戳入内容防 sha 去重) */
const png = (tag: string) => ({
  name: `e2e-${tag}.png`,
  mimeType: 'image/png',
  buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, ...Buffer.from(tag)])
})

/** 切换账号:清 token 回登录页最稳(已登录访问 /login 会被守卫弹回首页)。
 * 须先 goto 到 http 页再清 storage——test 初始 page 在 about:blank,localStorage 拒绝访问 */
async function logout(page: Page) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.goto('/login', { waitUntil: 'networkidle' })
}

/**
 * 登录。**每次都先清 storage**(实测残留 token 会让 /login 被路由守卫即刻弹回首页,
 * fill 的元素随导航销毁 → 60s 超时);先 goto 任一 http 页是因为 test 初始 page 在
 * about:blank,localStorage 拒绝访问。
 */
async function login(page: Page, username: string, password: string) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.goto('/login', { waitUntil: 'networkidle' })
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').first().fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).first().click()
  await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 20000 })
  await page.waitForTimeout(600)
}

test('Flow A 完整通过链:实验室+竞赛创建→学生提交→教师通过→成果库→学生证书', async ({ page }) => {
  // 1) admin 建实验室
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/laboratories')
  await page.getByRole('button', { name: '新增' }).click()
  // 搜索框与对话框字段同占位符,fill 须限定 .el-dialog 作用域
  await page.locator('.el-dialog').getByPlaceholder('请输入实验室名称').fill(`E2E实验室${TAG}`)
  await page.locator('.el-dialog').getByPlaceholder('请输入实验室描述').fill('批33 全功能测试')
  await page.locator('.el-dialog').getByRole('button', { name: '确 定' }).click()
  await expect(page.locator('body')).toContainText(`E2E实验室${TAG}`, { timeout: 8000 })

  // 2) admin 建竞赛
  await page.goto('/business/competitions')
  await page.getByRole('button', { name: '新增' }).click()
  await page.locator('.el-dialog').getByPlaceholder('请输入竞赛名称').fill(`E2E竞赛${TAG}`)
  await page.locator('.el-dialog').getByRole('button', { name: '确 定' }).click()
  await expect(page.locator('body')).toContainText(`E2E竞赛${TAG}`, { timeout: 8000 })
  await logout(page)

  // 3) 学生提交奖状(上传+动态字段)。类型选择是 el-radio-button(role=radio 非 button)
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/submit')
  await page.locator('.type-group .el-radio-button').filter({ hasText: '奖状' }).click()
  await page.locator('input[type="file"]').setInputFiles(png(TAG + 'a'))
  await page.getByPlaceholder('请输入竞赛名称').fill(`E2E竞赛${TAG}`)
  await page.getByPlaceholder('请输入获奖等级').fill('一等奖')
  await page.getByPlaceholder('请输入获奖人').fill('陈品天')
  await page.getByPlaceholder('请输入指导教师').fill('黄巧云')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.locator('.el-message').last()).toContainText('成功', { timeout: 10000 })
  // 我的提交出现待审核行
  await page.goto('/portal/submissions')
  await expect(page.locator('body')).toContainText(`E2E竞赛${TAG}`, { timeout: 8000 })
  await expect(page.locator('body')).toContainText('待审核')
  await logout(page)

  // 4) 教师初审通过
  await login(page, '02110606', 'P@ss301')
  await page.goto('/teacher/pending')
  await page.waitForTimeout(800)
  // 列表列不含竞赛名(achievement_data 不上列),不能 hasText 找行;
  // E2E 库教师相关 pending 仅此一行,取 first。行内应含"查看详情"操作
  const row = page.locator('.el-table__row').first()
  await expect(row).toBeVisible({ timeout: 8000 })
  await expect(row).toContainText('查看详情')
  await row.getByRole('button', { name: '通过' }).click()
  await page.locator('.el-dialog').getByRole('button', { name: /确\s*定|通\s*过/ }).last().click()
  // 待审页返回全部三态(状态为空不传):通过后行不消失、状态徽章变"已入库"
  await expect(row).toContainText('已入库', { timeout: 8000 })
  await logout(page)

  // 5) admin 成果库可见物化行
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/vault')
  await page.getByPlaceholder('按名称模糊搜索').fill(`E2E竞赛${TAG}`)
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.locator('.el-table__row', { hasText: `E2E竞赛${TAG}` }).first()).toBeVisible({ timeout: 8000 })

  // 6) 学生证书页渲染出该证书(文件真实存在,不走降级)
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/certificates')
  await expect(page.locator('body')).toContainText(`E2E竞赛${TAG}`, { timeout: 10000 })
  await expect(page.locator('body')).not.toContainText('证书加载失败', { timeout: 8000 })
})

test('Flow B 驳回链:学生提交→教师驳回→学生看到原因', async ({ page }) => {
  const tag = TAG + 'b'
  await logout(page)
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/submit')
  await page.locator('.type-group .el-radio-button').filter({ hasText: '专利' }).click()
  await page.locator('input[type="file"]').setInputFiles(png(tag))
  await page.getByPlaceholder('请输入专利名称').fill(`E2E专利${tag}`)
  await page.getByPlaceholder('请输入专利类型').fill('发明专利')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.locator('.el-message').last()).toContainText('成功', { timeout: 10000 })

  await logout(page)
  // 驳回走 admin(全量队列;专利无指导教师字段,教师姓名过滤看不到)
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/pending-achievements')
  await page.waitForTimeout(800)
  // E2E 库 pending 仅此一行(首行),列表列无专利名故不按文本找
  const row = page.locator('.el-table__row').first()
  await expect(row).toBeVisible({ timeout: 8000 })
  await expect(row).toContainText('查看详情')
  await row.getByRole('button', { name: '驳回' }).click()
  // 驳回必须填原因(BR-5)
  await page.locator('.el-dialog textarea, .el-dialog input[type="text"]').last().fill(`E2E驳回原因${tag}`)
  await page.locator('.el-dialog').getByRole('button', { name: /确\s*定|驳\s*回/ }).last().click()
  await expect(row).toContainText('已驳回', { timeout: 8000 })

  await logout(page)
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/submissions')
  await expect(page.locator('body')).toContainText(`E2E专利${tag}`, { timeout: 8000 })
  await expect(page.locator('body')).toContainText(`E2E驳回原因${tag}`, { timeout: 8000 })
})

test('Flow C 撤回:学生提交后撤回,队列消失', async ({ page }) => {
  const tag = TAG + 'c'
  await logout(page)
  await login(page, '212306413', 'P@ss301')
  await page.goto('/portal/submit')
  await page.locator('.type-group .el-radio-button').filter({ hasText: '软著' }).click()
  await page.locator('input[type="file"]').setInputFiles(png(tag))
  await page.getByPlaceholder('请输入软件名称').fill(`E2E软著${tag}`)
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.locator('.el-message').last()).toContainText('成功', { timeout: 10000 })
  await page.goto('/portal/submissions')
  await expect(page.locator('body')).toContainText(`E2E软著${tag}`, { timeout: 8000 })
  await page.getByRole('button', { name: '撤回' }).first().click()
  await page.locator('.el-message-box, .el-dialog').getByRole('button', { name: /确\s*定/ }).last().click()
  await page.waitForTimeout(800)
  await expect(page.locator('body')).not.toContainText(`E2E软著${tag}`, { timeout: 8000 })
})

test('Flow D 数据导出:下载 CSV 且非空', async ({ page }) => {
  await logout(page)
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/export')
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 15000 }),
    page.getByRole('button', { name: /下载/ }).first().click()
  ])
  expect(download.suggestedFilename()).toMatch(/\.(csv|xlsx)$/i)
  const path = await download.path()
  const fs = await import('node:fs')
  expect(fs.statSync(path!).size).toBeGreaterThan(50)
})

test('Flow E vault 行编辑:改获奖人保存后列表更新', async ({ page }) => {
  // 依赖 Flow A 物化的行
  await logout(page)
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/vault')
  await page.getByPlaceholder('按名称模糊搜索').fill(`E2E竞赛${TAG}`)
  await page.getByRole('button', { name: '搜索' }).click()
  const row = page.locator('.el-table__row', { hasText: `E2E竞赛${TAG}` }).first()
  await expect(row).toBeVisible({ timeout: 8000 })
  await row.getByRole('button', { name: '编辑' }).click()
  await page.locator('.el-dialog').getByPlaceholder('请输入获奖人').fill(`E2E改名人${TAG}`)
  await page.locator('.el-dialog').getByRole('button', { name: /确\s*定|保\s*存/ }).last().click()
  await expect(page.locator('body')).toContainText(`E2E改名人${TAG}`, { timeout: 8000 })
})

test('Flow F 批量导入:多图 AI 识别→提交→待审队列', async ({ page }) => {
  await logout(page)
  await login(page, 'admin', 'Mayy123')
  await page.goto('/business/bulk-import')
  await page.locator('input[type="file"]').setInputFiles([png(TAG + 'f1'), png(TAG + 'f2')])
  // fake 模式自动识别;识别成功的行**默认已勾选**(批18 设计),等"已勾选 2"直接提交
  await expect(page.locator('body')).toContainText('已识别 2', { timeout: 15000 })
  await expect(page.locator('body')).toContainText('已勾选 2', { timeout: 5000 })
  await page.getByRole('button', { name: /提交所选/ }).click()
  await expect(page.locator('.el-message').last()).toContainText('成功', { timeout: 10000 })
  // 待审管理出现队列行
  await page.goto('/business/pending-achievements')
  await page.waitForTimeout(1000)
  await expect(page.locator('.el-table__row').count()).resolves.toBeGreaterThan(0)
})
