<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Download } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// Fix-G 对照 v1 laboratories/downloads.html:文件列表表+计数徽标。
interface Dl {
  id: number
  fileTitle: string | null
  fileName: string | null
  file_size: number | null
  submitterType: string | null
  createdAt: string
}
const route = useRoute()
const id = Number(route.params.id)
const labName = ref('')
const rows = ref<Dl[]>([])
const loading = ref(true)

function fmtSize(n: number | null): string {
  return n ? (n / 1024).toFixed(1) + ' KB' : '-'
}

onMounted(async () => {
  const lab = await apiJson('GET', `/api/v2/admin/laboratories/${id}/detail`)
  if (lab.code === 0) labName.value = lab.data.name
  const body = await apiJson('GET', `/api/v2/admin/laboratories/${id}/downloads`)
  if (body.code === 0) rows.value = body.data.content
  loading.value = false
})
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <div>
        <h1 class="title">{{ labName }} - 下载专区</h1>
        <p class="sub">导出您关联的所有竞赛成果数据</p>
      </div>
    </div>

    <div class="c-panel pad">
      <div class="head-row">
        <h3 class="blk-title"><el-icon><Download /></el-icon> 下载文件列表</h3>
        <el-tag size="small">{{ rows.length }} 个文件</el-tag>
      </div>
      <el-table :data="rows" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="文件标题" min-width="220">
          <template #default="scope">
            {{ scope.row.fileTitle || scope.row.fileName || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="大小" width="110">
          <template #default="scope">
            {{ fmtSize(scope.row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="180">
          <template #default="scope">
            {{ scope.row.createdAt ? String(scope.row.createdAt).replace('T', ' ').slice(0, 19) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="scope">
            <el-icon class="dl-icon"><Download /></el-icon>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无可下载文件" />
        </template>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.title { font-size: 1.35rem; font-weight: 700; color: var(--ink); margin: 0 0 4px; }
.sub { font-size: 0.85rem; color: var(--ink-2); margin: 0 0 16px; }
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px;
}
.head-row {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
}
.blk-title {
  margin: 0; font-size: 1rem; font-weight: 600; color: var(--ink);
  display: inline-flex; align-items: center; gap: 6px;
}
.dl-icon { color: var(--brand); cursor: pointer; }
</style>
