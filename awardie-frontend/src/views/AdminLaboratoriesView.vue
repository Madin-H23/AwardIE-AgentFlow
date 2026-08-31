<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { OfficeBuilding } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #29 对照 v1 admin/laboratories/list.html:页头+创建按钮/实验室卡片网格(图片区+名称+简介)/空态。详情与编辑挂后续票。
interface Lab {
  id: number
  name: string
  description: string | null
  created_at: string
}
const rows = ref<Lab[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(12)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const body = await apiJson('GET', `/api/v2/admin/laboratories?page=${page.value}&size=${size.value}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <h1>实验室管理</h1>
      <el-tooltip content="实验室创建/编辑按批次迁移中">
        <span><el-button
          type="primary"
          disabled
        >创建实验室</el-button></span>
      </el-tooltip>
    </div>

    <div
      v-loading="loading"
      class="c-panel pad"
    >
      <div
        v-if="!rows.length && !loading"
        class="empty-state"
      >
        暂无实验室
      </div>
      <el-row :gutter="14">
        <el-col
          v-for="lab in rows"
          :key="lab.id"
          :span="8"
          style="margin-bottom: 14px"
        >
          <div class="lab-card">
            <div class="lab-cover">
              <el-icon :size="34">
                <OfficeBuilding />
              </el-icon>
            </div>
            <div class="lab-body">
              <div class="lab-name">
                {{ lab.name }}
              </div>
              <div class="lab-desc">
                {{ lab.description || '暂无简介' }}
              </div>
              <div class="lab-time">
                建于 {{ String(lab.created_at).slice(0, 10) }}
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
      <el-pagination
        v-if="total > size"
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        style="margin-top: 8px"
        @current-change="(p: number) => { page = p; load() }"
      />
    </div>
  </div>
</template>

<style scoped>
.lab-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.15s;
  cursor: default;
}
.lab-card:hover { border-color: var(--brand); }
.lab-cover {
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--brand) 8%, var(--panel));
  color: var(--brand);
}
.lab-body { padding: 12px 14px; }
.lab-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--ink);
}
.lab-desc {
  font-size: 0.8rem;
  color: var(--ink-2);
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.4em;
}
.lab-time {
  font-size: 0.72rem;
  color: var(--ink-2);
  margin-top: 8px;
}
.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--ink-2);
  font-size: 0.88rem;
}
</style>
