<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'
import {
  ArrowDown,
  DocumentChecked,
  House,
  Medal,
  Moon,
  Odometer,
  Sunny,
  SwitchButton,
  Trophy,
  Upload,
  User,
} from '@element-plus/icons-vue'
import { useTheme } from '../composables/useTheme'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { theme, toggle } = useTheme()

interface MenuItem {
  path: string
  label: string
  icon: Component
}
interface MenuGroup {
  title?: string
  items: MenuItem[]
}

// 对照 v1 layout/sidebar.html:admin 分组式(置顶总览+常用+基础数据管理),
// teacher/student 平铺;菜单只挂 v2 纵切面真实路由(v1 独有页不渲染,避免死链)。
const MENUS: Record<string, { overview?: MenuItem; groups: MenuGroup[] }> = {
  admin: {
    overview: { path: '/admin/dashboard', label: '数据总览', icon: Odometer },
    groups: [
      {
        title: '常用',
        items: [
          { path: '/admin/awards', label: '成果管理', icon: Medal },
          { path: '/teacher/review', label: '成果审核', icon: DocumentChecked },
        ],
      },
      {
        title: '基础数据管理',
        items: [{ path: '/admin/competitions', label: '竞赛管理', icon: Trophy }],
      },
    ],
  },
  teacher: {
    groups: [
      {
        items: [
          { path: '/', label: '教师首页', icon: House },
          { path: '/teacher/review', label: '成果审核', icon: DocumentChecked },
        ],
      },
    ],
  },
  student: {
    groups: [
      {
        items: [
          { path: '/', label: '学生首页', icon: House },
          { path: '/submit', label: '提交奖状', icon: Upload },
        ],
      },
    ],
  },
}

const menu = computed(() => MENUS[auth.user?.role ?? 'student'] ?? MENUS.student)
const collapsed = ref<Record<number, boolean>>({})

// 对照 v1 base_console 的 topbar_title 块:每页覆写标题
const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    home: '工作台',
    submit: '提交成果',
    'teacher-review': '成果审核',
    profile: '个人资料',
    'admin-awards': '成果管理',
    'admin-competitions': '竞赛管理',
    'admin-dashboard': '数据总览',
  }
  return titles[String(route.name)] ?? '控制台'
})

const avatarChar = computed(() => (auth.user?.name ?? '?').slice(0, 1).toUpperCase())

function isActive(path: string): boolean {
  return route.path === path
}

async function onUserCommand(command: string) {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    await auth.logout()
    router.push({ name: 'login' })
  }
}
</script>

<template>
  <div class="console-shell">
    <aside class="console-sidebar">
      <nav class="sidebar-nav">
        <template v-if="menu.overview">
          <router-link
            class="nav-link nav-overview"
            :class="{ active: isActive(menu.overview.path) }"
            :to="menu.overview.path"
          >
            <el-icon class="sb-ic">
              <component :is="menu.overview.icon" />
            </el-icon>{{ menu.overview.label }}
          </router-link>
          <hr class="sidebar-divider">
        </template>

        <template
          v-for="(group, gi) in menu.groups"
          :key="gi"
        >
          <div
            v-if="group.title"
            class="sb-group"
            :class="{ collapsed: collapsed[gi] }"
          >
            <div
              class="sb-group-title"
              @click="collapsed[gi] = !collapsed[gi]"
            >
              {{ group.title }}
              <el-icon class="sb-chevron">
                <ArrowDown />
              </el-icon>
            </div>
            <div class="sb-group-body">
              <router-link
                v-for="item in group.items"
                :key="item.path"
                class="nav-link"
                :class="{ active: isActive(item.path) }"
                :to="item.path"
              >
                <el-icon class="sb-ic">
                  <component :is="item.icon" />
                </el-icon>{{ item.label }}
              </router-link>
            </div>
          </div>
          <template v-else>
            <router-link
              v-for="item in group.items"
              :key="item.path"
              class="nav-link"
              :class="{ active: isActive(item.path) }"
              :to="item.path"
            >
              <el-icon class="sb-ic">
                <component :is="item.icon" />
              </el-icon>{{ item.label }}
            </router-link>
          </template>
          <hr
            v-if="gi < menu.groups.length - 1"
            class="sidebar-divider"
          >
        </template>
      </nav>

      <div class="sb-footer">
        <div class="sb-user">
          <el-icon><User /></el-icon>
          <span class="mono-data">{{ auth.user?.id }}</span>
          <span class="sb-role">{{ auth.user?.role }}</span>
        </div>
        <div class="sb-ver">
          AwardIE-AgentFlow 控制台 v2.0 · 管理端
        </div>
      </div>
    </aside>

    <header class="console-topbar">
      <span class="topbar-title">成果管理系统 · {{ pageTitle }}</span>
      <el-button
        class="theme-toggle"
        :icon="theme === 'dark' ? Sunny : Moon"
        :title="theme === 'dark' ? '切换为亮色模式' : '切换为深色模式'"
        data-testid="theme-toggle"
        @click="toggle"
      />
      <el-dropdown
        class="topbar-user"
        trigger="click"
        @command="onUserCommand"
      >
        <span
          class="topbar-user-btn"
          data-testid="topbar-user"
        >
          <span class="topbar-avatar">{{ avatarChar }}</span>
          <span class="topbar-username">{{ auth.user?.name }}</span>
          <el-icon class="topbar-caret"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              <div class="topbar-user-head">
                <div class="th-name">
                  {{ auth.user?.name }}
                </div>
                <div class="topbar-user-role">
                  {{ auth.user?.role }}
                </div>
              </div>
            </el-dropdown-item>
            <el-dropdown-item
              divided
              command="profile"
              :icon="User"
            >
              个人资料
            </el-dropdown-item>
            <el-dropdown-item
              command="logout"
              :icon="SwitchButton"
            >
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <main class="console-main">
      <router-view />
    </main>
  </div>
</template>
