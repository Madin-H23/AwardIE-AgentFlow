<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'
import {
  ArrowDown,
  Avatar,
  ChatDotRound,
  DataAnalysis,
  Document,
  DocumentChecked,
  Download,
  House,
  Medal,
  Moon,
  Odometer,
  OfficeBuilding,
  Postcard,
  Setting,
  Sunny,
  SwitchButton,
  Trophy,
  Upload,
  UploadFilled,
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
  /** 未迁移功能:落"迁移中"占位页,侧边栏仍全量对照 v1(#29) */
  soon?: boolean
}
interface MenuGroup {
  title?: string
  items: MenuItem[]
}

// 对照 v1 layout/sidebar.html 完整菜单结构(admin 六组);迁移完成项挂真实路由,
// 未迁移项带 soon 落占位页——菜单视觉完整且不撒谎。
const MENUS: Record<string, { overview?: MenuItem; groups: MenuGroup[] }> = {
  admin: {
    overview: { path: '/admin/dashboard', label: '数据总览', icon: Odometer },
    groups: [
      {
        title: '常用',
        items: [
          { path: '/admin/awards', label: '成果管理', icon: Medal },
          { path: '/admin/review', label: '成果审核', icon: DocumentChecked },
          { path: '/admin/logs', label: '日志管理', icon: Document },
        ],
      },
      {
        title: '智能体',
        items: [
          { path: '/chat', label: 'AI 智能体协作', icon: ChatDotRound },
        ],
      },
      {
        title: '基础数据管理',
        items: [
          { path: '/admin/import', label: '成果/文件导入', icon: UploadFilled },
          { path: '/admin/templates', label: '奖状模板管理', icon: Postcard },
          { path: '/admin/competitions', label: '竞赛管理', icon: Trophy },
          { path: '/admin/laboratories', label: '实验室管理', icon: OfficeBuilding },
        ],
      },
      {
        title: '用户数据',
        items: [
          { path: '/admin/students', label: '学生管理', icon: User },
          { path: '/admin/teachers', label: '教师管理', icon: Avatar },
          { path: '/admin/data-analysis', label: '数据分析', icon: DataAnalysis },
          { path: '/admin/data-export', label: '数据导出', icon: Download },
        ],
      },
      {
        title: '系统设置',
        items: [
          { path: '/admin/settings', label: '系统设置', icon: Setting },
        ],
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
    'admin-logs': '日志管理',
    'admin-students': '学生管理',
    'admin-teachers': '教师管理',
    'admin-laboratories': '实验室管理',
    'admin-templates': '奖状模板管理',
    'admin-data-analysis': '数据分析与导出',
    'admin-data-export': '数据导出',
    'admin-settings': '系统设置',
    chat: 'AI 智能体协作',
    'admin-import': '成果/文件导入',
    'coming-soon': '功能迁移',
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
                :class="{ active: isActive(item.path), soon: item.soon }"
                :to="item.path"
              >
                <el-icon class="sb-ic">
                  <component :is="item.icon" />
                </el-icon>{{ item.label }}
                <span
                  v-if="item.soon"
                  class="soon-chip"
                >迁移中</span>
              </router-link>
            </div>
          </div>
          <template v-else>
            <router-link
              v-for="item in group.items"
              :key="item.path"
              class="nav-link"
              :class="{ active: isActive(item.path), soon: item.soon }"
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
