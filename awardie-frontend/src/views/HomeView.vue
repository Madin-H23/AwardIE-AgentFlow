<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { apiJson } from '../composables/useCsrf'
import PageHeader from '../components/PageHeader.vue'
import {
  Avatar, ChatDotRound, DataAnalysis, Document, DocumentChecked, Download, Files, Medal,
  OfficeBuilding, Odometer, Postcard, Setting, Trophy, UploadFilled, User,
} from '@element-plus/icons-vue'

// UX-1 批2:工作台卡片化(诊断 B1:替换裸链接首页)。
// 入口与侧边栏同源(路径/文案照抄 ConsoleLayout 菜单);守卫下本页为 admin 专属(student/teacher 从 / 重定向门户)。
const auth = useAuthStore()
const router = useRouter()

interface Entry { path: string; label: string; icon: typeof Medal; desc: string }
interface Group { title: string; entries: Entry[] }

const groups: Group[] = [
  {
    title: '审核与成果',
    entries: [
      { path: '/admin/achievements', label: '成果管理', icon: Medal, desc: '全量成果五维度管理' },
      { path: '/admin/review', label: '成果审核', icon: DocumentChecked, desc: '审批提交与 AI 建议' },
      { path: '/admin/awards', label: '待审管理', icon: Document, desc: '待审记录状态跟踪' },
    ],
  },
  {
    title: '数据洞察',
    entries: [
      { path: '/admin/dashboard', label: '数据总览', icon: Odometer, desc: '资产条/汇总卡/趋势' },
      { path: '/admin/data-analysis', label: '数据分析', icon: DataAnalysis, desc: '竞赛与实验室分析' },
      { path: '/admin/data-export', label: '数据导出', icon: Download, desc: '年度总结 CSV' },
      { path: '/admin/logs', label: '日志管理', icon: Files, desc: '审核留痕与系统事件' },
    ],
  },
  {
    title: '基础数据',
    entries: [
      { path: '/admin/competitions', label: '竞赛管理', icon: Trophy, desc: '白名单唯一口径' },
      { path: '/admin/laboratories', label: '实验室管理', icon: OfficeBuilding, desc: '实验室与成员' },
      { path: '/admin/templates', label: '奖状模板管理', icon: Postcard, desc: 'AI 抽取模板' },
      { path: '/admin/students', label: '学生管理', icon: User, desc: '学生账号与归属' },
      { path: '/admin/teachers', label: '教师管理', icon: Avatar, desc: '教师账号' },
    ],
  },
  {
    title: 'AI 与工具',
    entries: [
      { path: '/chat', label: 'AI 智能体协作', icon: ChatDotRound, desc: '知识问答(RAG)' },
      { path: '/admin/import', label: '成果/文件导入', icon: UploadFilled, desc: '图片批量导入' },
      { path: '/admin/settings', label: '系统设置', icon: Setting, desc: '自动归档矩阵' },
    ],
  },
]

// 速览条:复用 #28 stats/overview 聚合(零后端改动);失败静默,不影响入口主链
interface Overview { summary: { totalAwards: number; pendingSubmit: number; competitions: number; whitelist: number } }
const stats = ref<Overview | null>(null)

onMounted(async () => {
  try {
    const body = await apiJson('GET', '/api/v2/admin/stats/overview')
    if (body.code === 0) {
      stats.value = body.data as Overview
    }
  } catch { /* 速览失败静默 */ }
})

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="home">
    <PageHeader
      title="工作台"
      :subtitle="auth.user ? `${auth.user.name} · 今天先看什么?` : '工作台'"
    >
      <template #actions>
        <el-button
          data-testid="home-profile"
          @click="$router.push('/profile')"
        >
          个人资料
        </el-button>
        <el-button
          data-testid="logout"
          type="danger"
          plain
          @click="logout"
        >
          登出
        </el-button>
      </template>
    </PageHeader>

    <!-- 速览条(#28 聚合;待审核>0 用警示色提示积压) -->
    <div
      v-if="stats"
      class="quick-stats"
    >
      <div class="stat">
        <span class="stat-num num">{{ stats.summary.totalAwards }}</span>
        <span class="stat-label">成果总数</span>
      </div>
      <div
        class="stat"
        :class="{ alert: stats.summary.pendingSubmit > 0 }"
      >
        <span class="stat-num num">{{ stats.summary.pendingSubmit }}</span>
        <span class="stat-label">待审核{{ stats.summary.pendingSubmit > 0 ? ' · 需处理' : ' · 无积压' }}</span>
      </div>
      <div class="stat">
        <span class="stat-num num">{{ stats.summary.competitions }}</span>
        <span class="stat-label">竞赛</span>
      </div>
      <div class="stat">
        <span class="stat-num num">{{ stats.summary.whitelist }}</span>
        <span class="stat-label">白名单竞赛</span>
      </div>
    </div>

    <!-- 入口分组卡(与侧边栏同源) -->
    <section
      v-for="g in groups"
      :key="g.title"
      class="entry-group"
    >
      <h2 class="group-title">
        {{ g.title }}
      </h2>
      <div class="entry-grid">
        <router-link
          v-for="e in g.entries"
          :key="e.path"
          :to="e.path"
          class="entry-card"
        >
          <el-icon
            :size="20"
            class="entry-icon"
          >
            <component :is="e.icon" />
          </el-icon>
          <span class="entry-label">{{ e.label }}</span>
          <span class="entry-desc">{{ e.desc }}</span>
        </router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home { padding: 4px 0; }

.quick-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-num {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.2;
}
.stat-label {
  font-size: var(--fs-cap);
  color: var(--ink-2);
}
.stat.alert .stat-num { color: var(--tag-warning); }

.group-title {
  font-size: var(--fs-section);
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 10px;
}
.entry-group { margin-bottom: 20px; }

.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.entry-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px 16px;
  text-decoration: none;
  transition: border-color .15s ease, transform .15s ease;
}
.entry-card:hover {
  border-color: var(--brand);
  transform: translateY(-1px);
}
.entry-icon { color: var(--brand); }
.entry-label {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--ink);
}
.entry-desc {
  font-size: var(--fs-cap);
  color: var(--ink-2);
}

@media (prefers-reduced-motion: reduce) {
  .entry-card,
  .entry-card:hover { transition: none; transform: none; }
}
</style>
