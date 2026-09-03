<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiJson } from '../composables/useCsrf'

// #29 对照 v1 admin/templates/main.html:页头/竞赛筛选 c-panel/模板列表(类型/语言/长度区间/关联竞赛)。
// v1 的 tab-detail(模板详情)与编辑挂后续票,本轮列表只读。
interface TemplateRow {
  id: number
  template_type: string
  language: string
  min_length: number
  max_length: number
  competition_id: number | null
  competition_name: string
}
interface Competition {
  id: number
  competitionName: string
}
const rows = ref<TemplateRow[]>([])
const competitions = ref<Competition[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const competitionId = ref<number | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams({ page: String(page.value), size: String(size.value) })
    if (competitionId.value) qs.set('competitionId', String(competitionId.value))
    const body = await apiJson('GET', `/api/v2/admin/templates?${qs}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

async function loadCompetitions() {
  const body = await apiJson('GET', '/api/v2/admin/competitions?page=1&size=100')
  if (body.code === 0) competitions.value = body.data.content
}

function pickCompetition() {
  page.value = 1
  load()
}

onMounted(() => {
  load()
  loadCompetitions()
})
</script>

<template>
  <div>
    <div class="page-head">
      <h1>奖状模板管理</h1>
      <router-link to="/admin/templates/create" data-testid="template-create-link">
        <el-button type="primary">新建模板</el-button>
      </router-link>
    </div>

    <div class="c-panel pad search-panel">
      <span class="label">按竞赛筛选</span>
      <el-select
        v-model="competitionId"
        placeholder="全部竞赛"
        clearable
        filterable
        style="width: 320px"
        data-testid="template-competition"
        @change="pickCompetition"
      >
        <el-option
          v-for="c in competitions"
          :key="c.id"
          :label="c.competitionName"
          :value="c.id"
        />
      </el-select>
    </div>

    <div class="c-panel pad">
      <el-tabs model-value="list">
        <el-tab-pane
          label="模板列表"
          name="list"
        >
          <el-table
            v-loading="loading"
            :data="rows"
            size="default"
          >
            <el-table-column
              prop="id"
              label="#"
              width="70"
            />
            <el-table-column
              prop="template_type"
              label="模板类型"
              width="120"
            />
            <el-table-column
              prop="language"
              label="语言"
              width="90"
            />
            <el-table-column label="抽取长度区间">
              <template #default="scope">
                <span class="mono">{{ scope.row.min_length }} ~ {{ scope.row.max_length }}</span>
              </template>
            </el-table-column>
            <el-table-column
              prop="competition_name"
              label="关联竞赛"
              min-width="220"
            />
            <el-table-column label="操作" width="100">
              <template #default="scope">
                <router-link :to="`/admin/templates/${scope.row.id}/detail`" data-testid="template-detail-link">
                  <el-button size="small" text type="primary">详情</el-button>
                </router-link>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            layout="prev, pager, next"
            :total="total"
            :page-size="size"
            :current-page="page"
            style="margin-top: 12px"
            @current-change="(p: number) => { page = p; load() }"
          />
        </el-tab-pane>
        <el-tab-pane
          label="模板详情"
          name="detail"
          lazy
        >
          <el-empty description="模板详情(样例图/抽取字段对照)按批次迁移中" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.search-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.label {
  font-size: 0.85rem;
  color: var(--ink-2);
}
.mono {
  font-variant-numeric: tabular-nums;
}
</style>
