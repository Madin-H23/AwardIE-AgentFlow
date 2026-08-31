<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

const API = '/api/v2/admin/competitions'
interface Competition {
  id: number
  competitionName: string
  whiteList: boolean
  watchList: boolean
  isAutoAdded: boolean
}
const rows = ref<Competition[]>([])
const q = ref('')
const newName = ref('')
const newWhite = ref(true)

async function load() {
  const body = await apiJson('GET', `${API}${q.value ? `?q=${encodeURIComponent(q.value)}` : ''}`)
  if (body.code === 0) rows.value = body.data
}
onMounted(load)

async function toggle(c: Competition) {
  const body = await apiJson('PUT', `${API}/${c.id}`, {
    competitionName: c.competitionName, whiteList: c.whiteList, watchList: c.watchList,
  })
  if (body.code === 0) ElMessage.success('已更新')
  else ElMessage.error(body.message)
}

async function create() {
  const body = await apiJson('POST', API, {
    competitionName: newName.value, whiteList: newWhite.value, watchList: false,
  })
  if (body.code === 0) {
    ElMessage.success('已创建')
    newName.value = ''
    await load()
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div class="comp-page">
    <el-card>
      <h2>竞赛管理(白名单 = BR-1 级别认定唯一口径)</h2>
      <div class="toolbar">
        <el-input
          v-model="q"
          placeholder="搜索竞赛名"
          style="width: 220px"
          clearable
          @change="load"
        />
        <el-input
          v-model="newName"
          placeholder="新竞赛名称"
          style="width: 220px"
        />
        <el-checkbox v-model="newWhite">
          白名单
        </el-checkbox>
        <el-button
          type="primary"
          :disabled="!newName"
          @click="create"
        >
          新建
        </el-button>
      </div>
      <el-table
        :data="rows"
        size="small"
        style="margin-top: 12px"
      >
        <el-table-column
          prop="id"
          label="#"
          width="80"
        />
        <el-table-column
          prop="competitionName"
          label="竞赛名称"
          min-width="220"
        />
        <el-table-column
          label="来源"
          width="110"
        >
          <template #default="scope">
            <el-tag
              :type="scope.row.isAutoAdded ? 'info' : 'success'"
              size="small"
            >
              {{ scope.row.isAutoAdded ? '自动建' : '手工' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="白名单"
          width="100"
        >
          <template #default="scope">
            <el-switch
              v-model="scope.row.whiteList"
              @change="toggle(scope.row, 'whiteList')"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="观察名单"
          width="110"
        >
          <template #default="scope">
            <el-switch
              v-model="scope.row.watchList"
              @change="toggle(scope.row, 'watchList')"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.comp-page { max-width: 1000px; margin: 24px auto; }
h2 { margin-top: 0; color: var(--ink); }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>
