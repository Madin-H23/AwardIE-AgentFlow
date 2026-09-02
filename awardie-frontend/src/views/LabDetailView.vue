<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { OfficeBuilding } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// Fix-G 对照 v1 laboratories/detail.html:头部卡(封面/名称/简介)+统计+教师/学生两列+下载入口。
interface Member { id: number; name: string; title?: string; grade?: string }
interface LabDetail {
  id: number
  name: string
  description: string | null
  coverImage: string | null
  createdAt: string
  instructors: Member[]
  students: Member[]
  downloadCount: number
  awardCount: number
}
const route = useRoute()
const id = Number(route.params.id)
const lab = ref<LabDetail | null>(null)
const loading = ref(true)

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/laboratories/${id}/detail`)
  if (body.code === 0) lab.value = body.data
  loading.value = false
})
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>实验室详情</h1>
      <div>
        <el-button @click="$router.push(`/admin/laboratories/${id}/edit`)">编辑</el-button>
        <el-button @click="$router.push(`/admin/laboratories/${id}/downloads`)">下载专区</el-button>
      </div>
    </div>

    <div class="card lab-header">
      <div class="lab-cover">
        <el-icon :size="42"><OfficeBuilding /></el-icon>
      </div>
      <div class="lab-head-info">
        <h2 class="lab-name">{{ lab?.name ?? '实验室' }}</h2>
        <p class="lab-desc">{{ lab?.description || '暂无简介' }}</p>
        <p class="lab-time">建于 {{ lab?.createdAt ? String(lab.createdAt).slice(0, 10) : '-' }}</p>
      </div>
    </div>

    <div class="stat-grid">
      <div class="card stat">
        <div class="num green">{{ lab?.awardCount ?? 0 }}</div>
        <div class="lbl">关联成果</div>
      </div>
      <div class="card stat">
        <div class="num orange">{{ lab?.students?.length ?? 0 }}</div>
        <div class="lbl">学生成员</div>
      </div>
      <div class="card stat">
        <div class="num blue">{{ lab?.instructors?.length ?? 0 }}</div>
        <div class="lbl">指导教师</div>
      </div>
      <div class="card stat">
        <div class="num purple">{{ lab?.downloadCount ?? 0 }}</div>
        <div class="lbl">下载文件</div>
      </div>
    </div>

    <div class="two-col">
      <div class="c-panel pad">
        <h3 class="blk-title">指导教师</h3>
        <div v-if="!lab?.instructors?.length" class="empty">暂无指导教师</div>
        <div v-for="t in lab?.instructors ?? []" :key="t.id" class="member">
          <span class="avatar-sm">{{ t.name.slice(0, 1) }}</span>
          <span>{{ t.name }}</span>
          <span class="muted">{{ t.title }}</span>
        </div>
      </div>
      <div class="c-panel pad">
        <h3 class="blk-title">学生成员</h3>
        <div v-if="!lab?.students?.length" class="empty">暂无学生成员</div>
        <div v-for="s in lab?.students ?? []" :key="s.id" class="member">
          <span class="avatar-sm">{{ s.name.slice(0, 1) }}</span>
          <span>{{ s.name }}</span>
          <span class="muted">{{ s.grade }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px; margin-bottom: 16px;
}
.lab-header {
  position: relative; overflow: hidden; border-radius: 12px;
  min-height: 200px; display: flex; align-items: flex-end;
  background: linear-gradient(to bottom, rgba(0,0,0,.05), rgba(0,0,0,.25)),
    color-mix(in srgb, var(--brand) 8%, var(--panel));
  margin-bottom: 16px;
}
.lab-cover {
  position: absolute; inset: 0; display: flex; align-items: center;
  justify-content: center; color: var(--brand); opacity: .35;
}
.lab-head-info { position: relative; padding: 20px; }
.lab-name { font-size: 1.8rem; font-weight: 700; color: var(--ink); margin: 0 0 6px; }
.lab-desc { color: var(--ink-2); font-size: 0.9rem; margin: 0 0 4px; }
.lab-time { color: var(--ink-2); font-size: 0.78rem; margin: 0; }
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.stat { text-align: center; }
.num { font-size: 1.7rem; font-weight: 700; }
.num.green { color: #16a34a; }
.num.orange { color: var(--portal-accent); }
.num.blue { color: #2563eb; }
.num.purple { color: #9333ea; }
.lbl { font-size: 0.82rem; color: var(--ink-2); margin-top: 4px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.blk-title { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.member {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 4px; border-bottom: 1px dashed var(--line); font-size: 0.9rem;
}
.avatar-sm {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  background: color-mix(in srgb, var(--portal-accent) 30%, var(--panel));
  color: var(--portal-accent); font-weight: 600; font-size: 0.8rem;
  display: inline-flex; align-items: center; justify-content: center;
}
.muted { margin-left: auto; color: var(--ink-2); font-size: 0.78rem; }
.empty { text-align: center; color: var(--ink-2); padding: 20px 0; font-size: 0.85rem; }
</style>
