# 07 — CI 前端门禁 + E2E

**What to build:** `ci-v3.yml` 加 `frontend-v3` job(`pnpm install` → `pnpm build:local` → `ts:check` → `lint`);引入 Playwright E2E 覆盖:登录 → 侧边栏九项(验动态路由机制,配错会白屏)→ 学生端三场景 → 375px 移动端。注意 CI 跑 Linux,与本地 Windows 有差异要验证(尤其 rolldown 原生模块的平台包)。

**Blocked by:** 03、04、05

**Status:** ready-for-agent

- [ ] CI 前端 job 绿(Linux)
- [ ] E2E 覆盖登录 + 九管理页 + 学生端三场景 + 375px
- [ ] 侧边栏动态渲染实测通过
- [ ] 本地与 CI 环境差异已记录
