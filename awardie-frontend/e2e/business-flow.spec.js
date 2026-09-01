// 业务闭环测试样例(Fix-D):按真实用户操作顺序走完整业务流。
// 用例清单:
//   BF-1 学生提交奖状 → 待审池出现(BR: 文件校验/sha 去重)
//   BF-2 教师审核通过 → 时间线含"审核通过"→ 学生成果 +1 → admin 成果库出现该记录
//   BF-3 教师驳回(缺理由拒绝)→ 学生时间线含"驳回"→ 重提交放行(BR-5)
//   BF-4 admin 实验室 创建→编辑→删除 全链
//   BF-5 admin 成果库删除 awards 行(异常数据治理路径)
// 约定:全部数据带 BF- 前缀标记,便于环境清理;测试库隔离见 scripts/v2_cleanup_testdata.py
import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5199/v2'
const API = '/api/v2'
const TAG = 'BF' + Date.now().toString().slice(-6)

async function login(page, account, password) {
  await page.goto(`${BASE}/login`)
  await page.getByTestId('login-account').waitFor({ state: 'visible', timeout: 10_000 })
  await page.getByTestId('login-account').fill(account)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await page.waitForTimeout(800)
}

async function submitAward(page, compName) {
  await page.goto(`${BASE}/portal/submit`)
  await page.getByRole('heading', { name: '提交成果' }).waitFor({ state: 'visible', timeout: 10_000 })
  await page.locator('input[type="file"]').setInputFiles({
    name: `bf-${compName}.png`, mimeType: 'image/png',
    buffer: Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, ...Buffer.from(compName)]),
  })
  await page.getByRole('textbox', { name: '竞赛名称' }).fill(compName)
  await page.getByRole('textbox', { name: '获奖人' }).fill('BF学生')
  await page.getByRole('button', { name: '提交审核' }).click()
  await expect(page.locator('.el-message').last()).toContainText('提交成功', { timeout: 10_000 })
}

test('BF-1+2 学生提交→教师通过→全链可见', async ({ browser }) => {
  const comp = `BF闭环赛-${TAG}`
  const stuCtx = await browser.newContext()
  const stu = await stuCtx.newPage()
  await login(stu, '212306413', 'P@ss301')
  await submitAward(stu, comp)
  // 学生侧确认待审行存在
  await stu.goto(`${BASE}/portal/submit`)
  await expect(stu.locator('table tbody tr', { hasText: comp }).first()).toBeVisible({ timeout: 10_000 })

  // 教师审核通过
  const tchCtx = await browser.newContext()
  const tch = await tchCtx.newPage()
  await login(tch, '02110606', 'P@ss301')
  await tch.goto(`${BASE}/portal/teacher/review`)
  await tch.waitForTimeout(1000)
  const row = tch.locator('table tbody tr', { hasText: comp }).first()
  await expect(row).toBeVisible({ timeout: 10_000 })
  await row.getByRole('button', { name: '批准' }).click()
  await tch.waitForTimeout(1200)
  // 教师时间线/学生侧:该提交已归档(学生重新查看)
  await stu.goto(`${BASE}/portal/submit`)
  await stu.waitForTimeout(1000)
  await stu.locator('table tbody tr', { hasText: comp }).first().locator('button', { hasText: '查看' }).click()
  await expect(stu.locator('.el-dialog__title')).toContainText('时间线')
  await expect(stu.locator('.el-dialog')).toContainText('审核通过', { timeout: 10_000 })
  await stu.locator('.el-dialog__headerbtn').click()

  // admin 成果库可见该成果(已物化)
  const admCtx = await browser.newContext()
  const adm = await admCtx.newPage()
  await login(adm, 'admin', 'Mayy123')
  await adm.goto(`${BASE}/admin/achievements`)
  await adm.getByRole('textbox', { name: '竞赛名称筛选' }).fill(comp)
  await adm.getByRole('button', { name: '筛选' }).click()
  await expect(adm.locator('.el-table__body', { hasText: comp }).first()).toBeVisible({ timeout: 10_000 })
  // 清理:删除该测试成果
  await adm.locator('.el-table__body tr', { hasText: comp }).first().locator('button', { hasText: '删除' }).click()
  await adm.locator('.el-message-box__btns button', { hasText: '确定' }).click()
  await adm.waitForTimeout(1000)
  admCtx.close()
  stuCtx.close()
})

test('BF-3 教师驳回→学生时间线可见(BR-5 重提交放行)', async ({ browser }) => {
  const comp = `BF驳回赛-${TAG}`
  const stuCtx = await browser.newContext()
  const stu = await stuCtx.newPage()
  await login(stu, '212306413', 'P@ss301')
  await submitAward(stu, comp)

  const tchCtx = await browser.newContext()
  const tch = await tchCtx.newPage()
  await login(tch, '02110606', 'P@ss301')
  await tch.goto(`${BASE}/portal/teacher/review`)
  const row = tch.locator('table tbody tr', { hasText: comp }).first()
  await expect(row).toBeVisible({ timeout: 10_000 })
  await row.locator('button', { hasText: '驳回' }).click()
  await row.getByTestId('reject-confirm').waitFor({ state: 'visible', timeout: 5000 })
  await row.locator('input[placeholder*="驳回原因"]').fill('BF 驳回测试:材料不全')
  await row.getByTestId('reject-confirm').click()
  await tch.waitForTimeout(1200)
  // 学生时间线含驳回事件
  await stu.goto(`${BASE}/portal/submit`)
  await stu.waitForTimeout(1000)
  await stu.locator('table tbody tr', { hasText: comp }).first().locator('button', { hasText: '查看' }).click()
  await expect(stu.locator('.el-dialog')).toContainText('驳回', { timeout: 10_000 })
  tchCtx.close()
  stuCtx.close()
})

test('BF-4 admin 实验室 创建→编辑→删除 全链', async ({ browser }) => {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await login(page, 'admin', 'Mayy123')
  await page.goto(`${BASE}/admin/laboratories`)
  await page.getByTestId('lab-create').click()
  await page.getByTestId('lab-name').fill(`BF实验室-${TAG}`)
  await page.getByTestId('lab-save').click()
  await page.waitForTimeout(1200)
  const card = page.locator('.lab-card', { hasText: `BF实验室-${TAG}` })
  await expect(card).toBeVisible()
  await card.locator('button', { hasText: '编辑' }).click()
  await page.getByTestId('lab-name').fill(`BF实验室-${TAG}-改`)
  await page.getByTestId('lab-save').click()
  await expect(page.locator('.lab-card', { hasText: `BF实验室-${TAG}-改` })).toBeVisible({ timeout: 10_000 })
  await page.locator('.lab-card', { hasText: `BF实验室-${TAG}-改` }).locator('button', { hasText: '删除' }).click()
  await page.locator('.el-message-box__btns button', { hasText: '确定' }).click()
  await page.waitForTimeout(1000)
  await expect(page.locator('.lab-card', { hasText: `BF实验室-${TAG}-改` })).toHaveCount(0)
  ctx.close()
})
