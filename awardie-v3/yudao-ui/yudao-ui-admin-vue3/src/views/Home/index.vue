<template>
  <div class="home">
    <div class="hero">
      <div class="hero__title">你好，{{ nickname }}</div>
      <!-- UX-2 批29:问候带真实待办——有待审时给行动入口,而不是静态欢迎语。
           用 RouterLink 而非 el-link:el-link 无 href 渲染成 <a href=undefined>,
           键盘不可达、无 Cmd/Ctrl+click(guidelines 合规审查抓出后改) -->
      <div
        v-if="pendingCount > 0"
        class="hero__todo"
        aria-live="polite"
      >
        有 <b>{{ pendingCount }}</b> 件成果待{{ isAdmin ? '复核' : '初审' }}
        <RouterLink :to="pendingPath" class="hero__todo-link">去处理</RouterLink>
      </div>
      <div v-else class="hero__sub">{{ roleLabel }}，欢迎使用 AwardIE 成果管理平台</div>
    </div>

    <el-row :gutter="16">
      <el-col v-for="entry in entries" :key="entry.path" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card shadow="hover" class="entry-card" @click="go(entry.path)">
          <div class="entry-card__icon">
            <Icon :icon="entry.icon" :size="26" />
          </div>
          <div class="entry-card__title">{{ entry.title }}</div>
          <div class="entry-card__desc">{{ entry.desc }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import request from '@/config/axios'

defineOptions({ name: 'Home' })

const router = useRouter()
const userStore = useUserStore()

const nickname = computed(() => userStore.getUser?.nickname || '用户')
const roles = computed(() => userStore.getRoles || [])

const isAdmin = computed(() => roles.value.some((r) => r === 'awardie_admin' || r === 'super_admin'))
const isTeacher = computed(() => roles.value.some((r) => r === 'awardie_teacher'))
const isStudent = computed(() => roles.value.some((r) => r === 'awardie_student'))

const roleLabel = computed(() => {
  if (isAdmin.value) return '管理员'
  if (isTeacher.value) return '教师'
  if (isStudent.value) return '学生'
  return '用户'
})

interface Entry {
  path: string
  icon: string
  title: string
  desc: string
}

/**
 * 每个角色只看到自己能进的入口。路径与后端菜单 SQL(system_menu.path)一致——
 * 侧边栏点得动,这里也得点得动,两处必须同源。
 */
const entries = computed<Entry[]>(() => {
  const list: Entry[] = []
  if (isStudent.value) {
    list.push(
      { path: '/portal/submit', icon: 'ep:upload', title: '提交成果', desc: '上传奖状或证书,填写信息' },
      { path: '/portal/submissions', icon: 'ep:list', title: '我的提交', desc: '查看审核进度与驳回原因' },
      { path: '/portal/certificates', icon: 'ep:document-checked', title: '我的证书', desc: '查看已获得的证书图片' }
    )
  }
  if (isTeacher.value) {
    list.push(
      { path: '/teacher/pending', icon: 'ep:document-checked', title: '待审成果', desc: '初审学生提交的成果' },
      { path: '/teacher/awards', icon: 'ep:trophy', title: '我的指导成果', desc: '我指导的获奖记录' }
    )
  }
  if (isAdmin.value) {
    list.push(
      { path: '/business/laboratories', icon: 'ep:office-building', title: '实验室管理', desc: '维护实验室基础数据' },
      { path: '/business/competitions', icon: 'ep:trophy', title: '竞赛管理', desc: '维护竞赛与白名单' },
      { path: '/business/pending-achievements', icon: 'ep:document-checked', title: '成果提交', desc: '复核与审核队列' },
      { path: '/business/vault', icon: 'ep:files', title: '成果库', desc: '五类已入库成果的查看与编辑' },
      { path: '/business/templates', icon: 'ep:price-tag', title: '证书模板', desc: 'AI 抽取规则配置' },
      { path: '/business/innovations', icon: 'ep:opportunity', title: '大创管理', desc: '项目维护、xlsx 导入、状态校准' },
      { path: '/business/stats', icon: 'ep:data-line', title: '统计分析', desc: '成果总量与竞赛战果' },
      { path: '/business/export', icon: 'ep:download', title: '数据导出', desc: '导出 CSV / Excel 交院里' },
      { path: '/business/logs', icon: 'ep:document', title: '业务日志', desc: '审核留痕追溯' }
    )
  }
  return list
})

const go = (path: string) => {
  router.push(path)
}

/**
 * 首页问候的待办数字:教师与管理员同源(teacher-pending-list 返回数组,批9 教训的 API 面)。
 * 失败静默(首页是仪表盘,接口挂了不该拦住入口卡)。
 */
const pendingCount = ref(0)
const pendingPath = computed(() => (isAdmin.value ? '/business/pending-achievements' : '/teacher/pending'))
onMounted(async () => {
  if (!isTeacher.value && !isAdmin.value) return
  try {
    const res: any = await request.get({
      url: '/business/pending-achievements/teacher-pending-list',
      params: { status: 'pending' }
    })
    pendingCount.value = Array.isArray(res) ? res.length : (res?.total ?? 0)
  } catch {
    /* 静默:问候行退回欢迎语 */
  }
})
</script>

<style scoped>
.home {
  padding: 8px;
}
.hero {
  margin-bottom: 16px;
}
.hero__title {
  font-size: 20px;
  font-weight: 600;
}
.hero__sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
/* UX-2 批29:待办行动问候 */
.hero__todo {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  b {
    color: var(--medal-gold);
    font-size: 15px;
  }
}
/* RouterLink 伪类链接样式(视觉对齐 EP link primary,带 focus-visible 焦点环) */
.hero__todo-link {
  margin-left: 6px;
  color: var(--el-color-primary);
  text-decoration: none;
  &:hover {
    color: var(--el-color-primary-light-3);
  }
  &:focus-visible {
    outline: 2px solid var(--el-color-primary);
    outline-offset: 2px;
    border-radius: 2px;
  }
}
.entry-card {
  margin-bottom: 16px;
  cursor: pointer;
  transition: transform 150ms ease;
}
.entry-card:hover {
  transform: translateY(-2px);
}
.entry-card__icon {
  color: var(--el-color-primary);
}
.entry-card__title {
  margin-top: 8px;
  font-size: 15px;
  font-weight: 600;
}
.entry-card__desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
