<template>
  <div class="portal-layout">
    <header class="portal-header">
      <div class="portal-header__brand">
        <Icon icon="ep:medal" :size="20" />
        <span class="portal-header__title">AwardIE 成果申报</span>
      </div>
      <el-dropdown trigger="click" @command="onCommand">
        <span class="portal-header__user">
          {{ userStore.getUser?.nickname || '未登录' }}
          <Icon icon="ep:arrow-down" :size="12" />
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <!-- 门户用底部 tab 导航而不是侧边栏:学生端 375px 为主,侧边栏在小屏要退化成抽屉,
         底部 tab 反而更符合拇指可达区,也不需要额外的开合状态 -->
    <nav class="portal-nav">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="portal-nav__item"
        active-class="is-active"
      >
        <Icon :icon="tab.icon" :size="18" />
        <span>{{ tab.label }}</span>
      </RouterLink>
    </nav>

    <main class="portal-main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'

defineOptions({ name: 'PortalLayout' })

const router = useRouter()
const userStore = useUserStore()

const tabs = [
  { path: '/portal/submit', label: '提交成果', icon: 'ep:upload' },
  { path: '/portal/submissions', label: '我的提交', icon: 'ep:list' },
  { path: '/portal/certificates', label: '我的证书', icon: 'ep:document-checked' }
]

const onCommand = async (command: string) => {
  if (command !== 'logout') {
    return
  }
  await userStore.loginOut()
  router.push('/login')
}
</script>

<style scoped>
.portal-layout {
  display: flex;
  flex-direction: column;
  /* 100dvh 而非 100vh:移动端浏览器地址栏收起/展开会改变 vh,dvh 才不会留缝 */
  min-height: 100dvh;
  background: var(--el-bg-color-page, #f5f7fa);
}
.portal-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 12px;
  background: var(--el-color-primary);
  color: #fff;
}
.portal-header__brand {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.portal-header__title {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.portal-header__user {
  display: flex;
  align-items: center;
  gap: 4px;
  /* 触控目标不小于 44px 的高 */
  min-height: 44px;
  padding: 0 4px;
  font-size: 14px;
  white-space: nowrap;
  cursor: pointer;
}
.portal-nav {
  position: sticky;
  top: 52px;
  z-index: 9;
  display: flex;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light, #e4e7ed);
}
.portal-nav__item {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 52px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  text-decoration: none;
}
.portal-nav__item.is-active {
  color: var(--el-color-primary);
  font-weight: 600;
}
.portal-main {
  flex: 1;
  padding: 12px;
  /* 底部留白,免得最后一块内容被 tab 栏压住 */
  padding-bottom: 24px;
}

/*
 * 触控目标 ≥44px(T05 验收项)。放在壳里而不是各页,是为了三页统一覆盖,
 * 也免得新加页面漏掉。必须用 :deep()——el-button 在子组件里,带的是子组件的
 * scope id,scoped 选择器不加 deep 命中不了(实测加完仍报 1 个 <44 就是这个原因)。
 * 430px 实测抓到「刷新」按钮只有 32px,这里一并兜住。
 */
.portal-main :deep(.el-button) {
  min-height: 44px;
}
</style>
