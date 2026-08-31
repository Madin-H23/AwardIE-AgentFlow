<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { apiJson } from '../composables/useCsrf'

// #35 师生门户壳(对照 v1 user_base.html:顶部固定导航+内容区;区别于 admin 的 Console 侧边栏)。
// v1 师生主色 orange;导航项按角色:仪表板/成果展示/成果提交/[教师:成果审核]/AI 助手/个人资料。

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

interface NavItem {
  path: string
  label: string
}
const navItems = computed<NavItem[]>(() => {
  if (auth.user?.role === 'teacher') {
    return [
      // 教师仪表板(Goal D)上线后补首位
      { path: '/teacher/achievements', label: '成果展示' },
      { path: '/teacher/review', label: '成果审核' },
      { path: '/chat', label: 'AI 助手' },
      { path: '/profile', label: '个人资料' },
    ]
  }
  return [
    { path: '/student/dashboard', label: '仪表板' },
    { path: '/student/achievements', label: '成果展示' },
    { path: '/submit', label: '成果提交' },
    { path: '/chat', label: 'AI 助手' },
    { path: '/profile', label: '个人资料' },
  ]
})

const activePath = computed(() => '/' + route.path.replace(/^\//, ''))

function isActive(item: NavItem): boolean {
  return route.path === item.path || route.path.startsWith(item.path + '/')
}

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="portal-shell-min">
    <nav class="portal-nav">
      <div class="nav-inner">
        <span class="brand">成果管理系统</span>
        <div class="nav-links">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item) }"
          >
            {{ item.label }}
          </router-link>
        </div>
        <div class="nav-user">
          <span class="user-chip">{{ auth.user?.name }}</span>
          <button
            class="logout"
            data-testid="portal-logout"
            @click="logout"
          >
            登出
          </button>
        </div>
      </div>
    </nav>

    <main class="portal-main">
      <div class="portal-container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.portal-shell-min {
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
}
.portal-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1020;
  background: color-mix(in srgb, var(--panel) 90%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.nav-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 16px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 22px;
}
.brand {
  font-weight: 700;
  font-size: 1.02rem;
  color: var(--ink);
  white-space: nowrap;
}
.nav-links {
  display: flex;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
}
.nav-item {
  padding: 19px 4px;
  font-size: 0.9rem;
  color: var(--ink-2);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: color 0.2s;
}
.nav-item:hover { color: var(--portal-accent); }
.nav-item.active {
  color: var(--portal-accent);
  font-weight: 500;
  border-bottom-color: var(--portal-accent);
}
.nav-user {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-chip { font-size: 0.85rem; color: var(--ink-2); }
.logout {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.8rem;
  cursor: pointer;
}
.logout:hover { color: var(--portal-accent); border-color: var(--portal-accent); }

.portal-main { padding-top: 60px; }
.portal-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px 16px 40px;
}
</style>
