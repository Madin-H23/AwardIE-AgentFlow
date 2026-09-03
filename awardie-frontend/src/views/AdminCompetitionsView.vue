<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'
import { useTablePage } from '../composables/useTablePage'
import PageHeader from '../components/PageHeader.vue'

const API = '/api/v2/admin/competitions'
interface Competition {
  id: number
  competitionName: string
  whiteList: boolean
  watchList: boolean
  isAutoAdded: boolean
}

// #27:useTablePage 统一分页+筛选(q 竞赛名模糊)+loading
const tp = useTablePage<Competition>({ api: API, filters: { q: '' } })

const newName = ref('')
const newWhite = ref(true)

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
    await tp.load()
  } else {
    ElMessage.error(body.message)
  }
}
onMounted(tp.load)
</script>

<template>
  <div class="comp-page">
    <el-card>
      <!-- UX-1 批1:PageHeader 示范接入(批3 全量推广) -->
      <PageHeader
        title="竞赛管理"
        subtitle="白名单 = BR-1 级别认定唯一口径"
      />
      <div class="toolbar">
        <el-input
          v-model="tp.filters.q"
          placeholder="搜索竞赛名"
          style="width: 220px"
          clearable
          data-testid="comp-q"
          @keyup.enter="tp.search()"
          @clear="tp.search()"
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
        v-loading="tp.loading.value"
        :data="tp.rows.value"
        size="small"
        style="margin-top: 12px"
      >
        <el-table-column
          prop="id"
          label="#"
          width="80"
          class-name="num"
        />
        <el-table-column
          prop="competitionName"
          label="竞赛名称"
          min-width="220"
        >
          <template #default="scope">
            <el-link
              type="primary"
              :href="`/v2/admin/competitions/${scope.row.id}`"
              data-testid="comp-detail-link"
            >
              {{ scope.row.competitionName }}
            </el-link>
          </template>
        </el-table-column>
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
              @change="toggle(scope.row)"
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
              @change="toggle(scope.row)"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        layout="prev, pager, next"
        :total="tp.total.value"
        :page-size="tp.size.value"
        :current-page="tp.page.value"
        style="margin-top: 12px"
        @current-change="tp.go"
      />
    </el-card>
  </div>
</template>

<style scoped>
.comp-page { }
h2 { margin-top: 0; color: var(--ink); }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>
