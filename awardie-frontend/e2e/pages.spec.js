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

async function loginAsStudent(page) {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('212306413')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await page.locator('.portal-nav').waitFor({ state: 'visible', timeout: 10_000 })
}

test('工作台卡片化渲染(UX-1 批2)', async ({ page }) => {
  await loginAsAdmin(page)
  await expect(page.locator('.home')).toContainText('审核与成果')
  await expect(page.locator('.home')).toContainText('数据洞察')
  await expect(page.locator('.home .entry-card', { hasText: '数据总览' })).toBeVisible()
  await expect(page.getByTestId('logout')).toBeVisible()
})

test('提交页含表单/我的提交/我的成果', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/submit`)
  await expect(page.getByRole('heading', { name: '提交成果' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的提交' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的成果(已入库)' })).toBeVisible()
})

test('时间线对话框展示事件', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/submit`)
  // 自给自足:先提交一笔(文件掺时间戳防 sha 去重),再开时间线
  const tag = String(Date.now())
  await page.locator('input[type="file"]').setInputFiles({
    name: `tl-${tag}.png`, mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, ...Buffer.from(tag)]),
  })
  await page.getByRole('textbox', { name: '竞赛名称' }).fill(`时间线E2E赛-${tag}`)
  await page.getByRole('textbox', { name: '获奖人' }).fill('时间线学生')
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.locator('.el-message').last()).toContainText('提交成功', { timeout: 10_000 })
  await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10_000 })
  await page.locator('button', { hasText: '查看' }).first().click()
  await expect(page.locator('.el-dialog__title')).toContainText('时间线')
  await expect(page.locator('.el-timeline, .el-empty').first()).toBeVisible({ timeout: 10_000 })
})

test('教师审核台渲染(admin 视角)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/teacher/review`)
  await expect(page.getByRole('heading', { name: '待审列表' })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
})

test('未匹配路由落 404 兜底页(Fix-U)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/no-such-page-xyz`)
  await expect(page.getByRole('heading', { name: '404' })).toBeVisible()
  await expect(page.locator('.nf-panel a', { hasText: '返回首页' })).toBeVisible()
})

test('审核台已审行不再渲染审核按钮(Fix-V)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/teacher/review`)
  await expect(page.locator('table tbody tr').first()).toBeVisible()
  // 结构层断言:已审行(已归档/已驳回,批3 徽章化后为中文)内不出现批准/驳回按钮;无已审行时空态兼容
  const reviewed = page.locator('table tbody tr', { hasText: /已归档|已驳回|archived|rejected/ })
  await expect(reviewed.locator('button', { hasText: '批准' })).toHaveCount(0)
  await expect(reviewed.locator('button', { hasText: '驳回' })).toHaveCount(0)
})

test('个人资料按角色渲染字段', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/profile`)
  await expect(page.getByRole('heading', { name: /个人资料/ })).toBeVisible()
  await expect(page.getByTestId('profile-name')).toBeVisible()
})

test('admin 待审管理渲染(UX-1 批3 标题对齐)', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/awards`)
  await expect(page.getByRole('heading', { name: '待审管理' })).toBeVisible()
  // 类型/状态列中文徽章化(消灭英文工程值直出)
  await expect(page.locator('.el-table').locator('tbody tr').first()).toBeVisible()
  await expect(page.locator('.el-tag', { hasText: '待审' }).first()).toBeVisible()
})

test('侧边栏含工作台入口(UX-1 批3)', async ({ page }) => {
  await loginAsAdmin(page)
  const sidebar = page.locator('.console-sidebar')
  await expect(sidebar.locator('.nav-overview', { hasText: '工作台' })).toBeVisible()
  await expect(sidebar.locator('.nav-link', { hasText: '数据总览' }).first()).toBeVisible()
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
  // UX-1 批4:汇总卡左栏改"本月新增"(去 grandTotal 重复)
  await expect(page.getByText('本月新增')).toBeVisible()
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

test('未迁移占位路由可直达', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/coming-soon?title=测试占位`)
  await expect(page.getByRole('heading', { name: /迁移中/ })).toBeVisible()
})

// Goal A 第二批:#30-#32 三页冒烟
test('数据分析三tab渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/data-analysis`)
  await expect(page.getByRole('heading', { name: '数据分析与导出' })).toBeVisible()
  await expect(page.locator('.el-tabs__item', { hasText: '竞赛分析' })).toBeVisible()
  await page.locator('.el-tabs__item', { hasText: '竞赛分析' }).click()
  // CI 空库年份池为空(year-tags 零高度),断言恒在的筛选面板
  await expect(page.locator('.filter-panel')).toBeVisible({ timeout: 10_000 })
})

test('数据导出页渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/data-export`)
  await expect(page.getByRole('heading', { name: '数据导出' })).toBeVisible()
  await expect(page.getByTestId('export-summary')).toBeVisible()
})

test('系统设置自动归档矩阵渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/settings`)
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  await page.locator('.el-tabs__item', { hasText: '自动归档' }).click()
  await expect(page.getByTestId('settings-save')).toBeVisible({ timeout: 10_000 })
})

// Goal B:#33/#34 两页冒烟
test('智能体页 fake 对话渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/chat`)
  await expect(page.getByRole('heading', { name: /AI 智能助手/ })).toBeVisible()
  await page.getByTestId('chat-input').fill('白名单赛事有哪些?')
  await page.getByTestId('chat-send').click()
  await expect(page.getByTestId('chat-messages')).toContainText('fake 模式', { timeout: 15_000 })
})

test('导入页上传区渲染', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/import`)
  await expect(page.getByRole('heading', { name: '成果/文件导入' })).toBeVisible()
  await expect(page.locator('.el-upload')).toBeVisible()
})

// Goal 修复批:Fix-B 守卫与 D2 教师提交
test('守卫:admin 访问学生提交页被重定向', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/portal/submit`)
  await page.waitForTimeout(1000)
  // admin 越权访问学生页 → 重定向回 admin 首页(不显示学生提交表单)
  expect(page.url()).not.toContain('/portal/submit')
})

test('教师提交通道可用(D2)', async ({ page }) => {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').fill('02110606')
  await page.getByTestId('login-password').fill('P@ss301')
  await page.getByTestId('login-submit').click()
  await page.locator('.portal-nav').waitFor({ state: 'visible', timeout: 10_000 })
  await page.goto(`${BASE}/portal/submit`)
  await page.getByRole('heading', { name: '提交成果' }).waitFor({ state: 'visible', timeout: 10_000 })
  // 尾部掺时间戳:sha 每次不同,避免跨运行去重拦截
  const pngBytes = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x54, 0x45,
    ...Buffer.from(String(Date.now()))])
  await page.locator('input[type="file"]').setInputFiles({
    name: 'teacher-e2e.png', mimeType: 'image/png', buffer: pngBytes,
  })
  await page.getByRole('textbox', { name: '竞赛名称' }).fill('教师提交E2E赛')
  await page.getByRole('textbox', { name: '获奖人' }).fill('巡检教师')
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.locator('.el-message').last()).toContainText('提交成功', { timeout: 10_000 })
})

// G4 交互深度增补
test('G4-1 提交表单校验:未选文件/缺必填的提示', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/portal/submit`)
  await page.getByRole('button', { name: '提交审核' }).waitFor({ state: 'visible', timeout: 10_000 })
  // 未选文件直接提交
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.locator('.el-message').last()).toContainText('请选择', { timeout: 10_000 })
  // 选文件但竞赛名称为空
  await page.locator('input[type="file"]').setInputFiles({
    name: 'g4.png', mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, ...Buffer.from(String(Date.now()))]),
  })
  await page.getByRole('button', { name: '提交审核' }).click()
  // v1 语义:竞赛名称缺失属 completeness 警告非阻断——提交成功但带校验提示
  await expect(page.locator('.el-message').last()).toContainText('提交成功', { timeout: 10_000 })
})

test('G4-2 成果待审管理翻页内容变化', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/awards`)
  await expect(page.locator('.el-table').locator('tbody tr').first()).toBeVisible({ timeout: 10_000 })
  const firstId = await page.locator('.el-table__body tr').first().locator('td').first().innerText()
  const next = page.locator('.el-pagination .btn-next')
  if (await next.count() && !(await next.isDisabled())) {
    await next.click()
    await page.waitForTimeout(800)
    const newFirst = await page.locator('.el-table__body tr').first().locator('td').first().innerText()
    expect(newFirst).not.toBe(firstId)
  } else {
    // 单页数据:分页不可点也算通过(无翻页语义)
    expect(await page.locator('.el-pagination').count()).toBeGreaterThan(0)
  }
})

test('G4-3 学生撤回后行消失', async ({ page }) => {
  await loginAsStudent(page)
  const tag = String(Date.now())
  await page.goto(`${BASE}/portal/submit`)
  await page.getByRole('button', { name: '提交审核' }).waitFor({ state: 'visible', timeout: 10_000 })
  await page.locator('input[type="file"]').setInputFiles({
    name: `g4wd-${tag}.png`, mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, ...Buffer.from(tag)]),
  })
  await page.getByRole('textbox', { name: '竞赛名称' }).fill(`G4撤回赛-${tag}`)
  await page.getByRole('textbox', { name: '获奖人' }).fill('撤回学生')
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.locator('.el-message').last()).toContainText('提交成功', { timeout: 10_000 })
  const row = page.locator('table tbody tr', { hasText: `G4撤回赛-${tag}` }).first()
  await row.locator('button', { hasText: '撤回' }).click()
  await page.locator('.el-message-box__btns button', { hasText: '确定' }).click()
  await page.waitForTimeout(1000)
  await expect(page.locator('table tbody tr', { hasText: `G4撤回赛-${tag}` })).toHaveCount(0)
})

test('G4-4 刷新后守卫态保持', async ({ page }) => {
  await loginAsStudent(page)
  await page.goto(`${BASE}/portal/submit`)
  await page.getByRole('heading', { name: '提交成果' }).waitFor({ state: 'visible', timeout: 10_000 })
  await page.reload()
  await page.waitForTimeout(1000)
  await expect(page.getByRole('heading', { name: '提交成果' })).toBeVisible()
  expect(page.url()).toContain('/portal/submit')
})

test('G4-5 暗色主题三代表页截图留档', async ({ page }) => {
  await loginAsStudent(page)
  // portal 无主题钮:经 localStorage 置暗色后刷新生效(useTheme 读 theme 键)
  await page.evaluate(() => localStorage.setItem('theme', 'dark'))
  for (const [name, path] of [
    ['dark-student-dashboard', '/portal/student/dashboard'],
    ['dark-awards', '/admin/awards'],
    ['dark-settings', '/admin/settings'],
  ]) {
    await page.goto(`${BASE}${path}`)
    await page.waitForTimeout(900)
    await page.screenshot({ path: `../docs/重构二期/03-对照验收/暗色/G4-${name}.png` })
  }
})

// UX-1 批5:亮色主题核查(默认主题)+表格 hover 实证 + dashboard 主题切换重绘
test('UX-5 亮色主题核查与表格 hover 实证', async ({ page }) => {
  await loginAsAdmin(page)
  await page.evaluate(() => localStorage.setItem('theme', 'light'))
  for (const [name, path] of [
    ['light-workbench', '/'],
    ['light-dashboard', '/admin/dashboard'],
    ['light-awards-pending', '/admin/awards'],
  ]) {
    await page.goto(`${BASE}${path}`)
    await page.waitForTimeout(900)
    await expect(page.locator('.console-shell, .home').first()).toBeVisible()
    await page.screenshot({ path: `../docs/重构二期/06-体验重设计/05-批5双壳一致性与亮色核查/${name}.png` })
  }
  // 表格 hover 实证:hover 色刷在 td 不在 tr(tr 恒为面板底色,读 tr 得恒真断言)
  await page.goto(`${BASE}/admin/competitions`)
  await page.waitForTimeout(800)
  const row = page.locator('.el-table__body tr').first()
  const cell = row.locator('td').first()
  const beforeHover = await cell.evaluate((el) => getComputedStyle(el).backgroundColor)
  await row.hover()
  await page.waitForTimeout(300)
  const afterHover = await cell.evaluate((el) => getComputedStyle(el).backgroundColor)
  expect(afterHover).not.toBe(beforeHover)
  expect(afterHover).not.toBe('rgba(0, 0, 0, 0)')
  // 主题切换 chart 重绘:切暗刷新出图后点顶栏切回亮色——不刷新走 watch(dispose+重建),canvas 必须重新可见
  await page.goto(`${BASE}/admin/dashboard`)
  await page.evaluate(() => localStorage.setItem('theme', 'dark'))
  await page.reload()
  await page.waitForTimeout(900)
  await expect(page.locator('.dash-page canvas').first()).toBeVisible({ timeout: 10_000 })
  await page.getByTestId('theme-toggle').click()
  await expect(page.locator('.dash-page canvas').first()).toBeVisible({ timeout: 10_000 })
})

// UX-2 挂账小批:筛选折叠(B5)+徽章化/.num 推广+analysis 双页主题重绘
test('UX-6 筛选折叠、徽章化推广与 analysis 主题重绘', async ({ page }) => {
  await loginAsAdmin(page)
  // 待审管理:七维高级筛选默认折叠,展开后可见且查询链路不受影响
  await page.goto(`${BASE}/admin/awards`)
  await page.waitForTimeout(800)
  const yearFilter = page.getByPlaceholder('如 2026')
  await expect(yearFilter).toBeHidden()
  await page.getByTestId('filter-advanced-toggle').click()
  await expect(yearFilter).toBeVisible()
  await page.getByTestId('filter-search').click()
  await expect(page.locator('.el-table').first()).toBeVisible()
  // 徽章化推广:类型/状态列为中文 tag;提交者类型不再是裸英文值
  await expect(page.locator('.el-table .el-tag').first()).toBeVisible()
  await expect(page.locator('.el-table').first()).not.toContainText('student')
  // 留档:折叠态与展开态各一张(G4-5/UX-5 同款测试内截图惯例)
  await page.getByTestId('filter-advanced-toggle').click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: '../docs/重构二期/06-体验重设计/06-批6挂账小批/awards-filter-collapsed.png' })
  await page.getByTestId('filter-advanced-toggle').click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: '../docs/重构二期/06-体验重设计/06-批6挂账小批/awards-filter-expanded.png' })
  // analysis 主题切换重绘:切主题后当前 tab chart 重建(canvas 重新可见)
  await page.goto(`${BASE}/admin/data-analysis`)
  await page.waitForTimeout(900)
  await expect(page.locator('canvas').first()).toBeVisible({ timeout: 10_000 })
  await page.getByTestId('theme-toggle').click()
  await expect(page.locator('canvas').first()).toBeVisible({ timeout: 10_000 })
  await page.getByTestId('theme-toggle').click()
})

// Worker RPC 页面批次(架构票交付物 5):模板创建页 AI 主链(fake 模式,CI 确定性)
test('UX-7 模板创建页 AI 抽取与提示词生成主链', async ({ page }) => {
  await loginAsAdmin(page)
  await page.goto(`${BASE}/admin/templates/create`)
  await page.getByTestId('tpl-create-competition').click()
  await page.locator('.el-select-dropdown__item').first().click()
  await page.locator('input[type="file"]').setInputFiles({
    name: `tpl7-${Date.now()}.png`, mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
  })
  // AI 抽取:回填样本抽取值(fake 桩固定文案;键名契约 dataJson/ocrText/mode)
  await page.getByTestId('tpl-ai-extract').click()
  await expect(page.getByTestId('tpl-create-extracted')).toHaveValue(/示例竞赛/, { timeout: 10_000 })
  // 生成提示词:预览区出现(fake 桩 prompt 含样本文本回显)
  await page.getByTestId('tpl-ai-prompt').click()
  await expect(page.getByTestId('tpl-prompt-preview')).toBeVisible({ timeout: 10_000 })
  await expect(page.getByTestId('tpl-prompt-preview')).toHaveValue(/OCR/)
  await page.screenshot({ path: '../docs/重构二期/06-体验重设计/07-Worker-RPC页面批次/tpl-create-ai-chain.png', fullPage: true })
})
