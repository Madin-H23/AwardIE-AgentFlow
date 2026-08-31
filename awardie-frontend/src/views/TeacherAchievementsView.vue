<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// Goal D 对照 v1 teacher/achievements_ref.html:三统计卡(国家级/省级/总获奖)+四维筛选+奖状表格+导出当前筛选。

interface Row {
  id: number
  competition: string | null
  level: string | null
  awardLevel: string | null
  year: string | null
  winnerName: string | null
}
interface Comp {
  id: number
  competitionName: string
}
const rows = ref<Row[]>([])
const totalNational = ref(0)
const totalProvincial = ref(0)
const totalAwards = ref(0)
const competitions = ref<Comp[]>([])
const competitionId = ref<number | null>(null)
const year = ref('')
const competitionLevel = ref('')
const awardLevel = ref('')
const loading = ref(false)

const LEVELS = ['校赛', '区域赛', '省赛', '国赛', '国际赛']
const AWARDS = ['特等奖', '一等奖', '二等奖', '三等奖', '优秀奖']

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams()
    if (competitionId.value) qs.set('competitionId', String(competitionId.value))
    if (year.value) qs.set('year', year.value)
    if (competitionLevel.value) qs.set('competitionLevel', competitionLevel.value)
    if (awardLevel.value) qs.set('awardLevel', awardLevel.value)
    const body = await apiJson('GET', `/api/v2/teacher/portal/achievements?${qs}`)
    if (body.code === 0) {
      rows.value = body.data.rows
      totalNational.value = body.data.totalNational
      totalProvincial.value = body.data.totalProvincial
      totalAwards.value = body.data.totalAwards
    }
  } finally {
    loading.value = false
  }
}

async function loadCompetitions() {
  const body = await apiJson('GET', '/api/v2/admin/competitions?page=1&size=100')
  if (body.code === 0) competitions.value = body.data.content
}

function exportFiltered() {
  const qs = new URLSearchParams()
  if (year.value) qs.set('year', year.value)
  const a = document.createElement('a')
  a.href = `/api/v2/teacher/portal/export.csv?${qs}`
  a.download = 'teacher-achievements.csv'
  a.click()
}

onMounted(() => {
  load()
  loadCompetitions()
})
</script>

<template>
  <div>
    <div class="page-head">
      <h1>成果展示</h1>
      <el-button
        :icon="Download"
        data-testid="teacher-export"
        @click="exportFiltered"
      >
        导出当前筛选数据
      </el-button>
    </div>

    <!-- 三统计卡 -->
    <div class="stat-grid">
      <div class="card stat">
        <div class="num yellow">
          {{ totalNational }}
        </div>
        <div class="lbl">
          国家级获奖
        </div>
      </div>
      <div class="card stat">
        <div class="num blue">
          {{ totalProvincial }}
        </div>
        <div class="lbl">
          省级获奖
        </div>
      </div>
      <div class="card stat">
        <div class="num green">
          {{ totalAwards }}
        </div>
        <div class="lbl">
          总获奖(当前筛选)
        </div>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="card filters">
      <el-select
        v-model="competitionId"
        placeholder="全部竞赛"
        clearable
        filterable
        style="width: 240px"
        @change="load"
      >
        <el-option
          v-for="c in competitions"
          :key="c.id"
          :label="c.competitionName"
          :value="c.id"
        />
      </el-select>
      <el-input
        v-model="year"
        placeholder="年份"
        style="width: 110px"
        clearable
        @keyup.enter="load"
        @clear="load"
      />
      <el-select
        v-model="competitionLevel"
        placeholder="竞赛级别"
        clearable
        style="width: 130px"
        @change="load"
      >
        <el-option
          v-for="lv in LEVELS"
          :key="lv"
          :label="lv"
          :value="lv"
        />
      </el-select>
      <el-select
        v-model="awardLevel"
        placeholder="获奖等级"
        clearable
        style="width: 130px"
        @change="load"
      >
        <el-option
          v-for="lv in AWARDS"
          :key="lv"
          :label="lv"
          :value="lv"
        />
      </el-select>
    </div>

    <!-- 表格 -->
    <div class="card">
      <el-table
        v-loading="loading"
        :data="rows"
        size="small"
      >
        <el-table-column
          prop="competition"
          label="竞赛名称"
          min-width="240"
        />
        <el-table-column
          prop="level"
          label="竞赛级别"
          width="110"
        />
        <el-table-column
          prop="awardLevel"
          label="获奖等级"
          width="110"
        />
        <el-table-column
          prop="winnerName"
          label="获奖人"
          width="120"
        />
        <el-table-column
          prop="year"
          label="年份"
          width="80"
        />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.page-head h1 { font-size: 1.35rem; font-weight: 700; color: var(--ink); margin: 0; }
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px; margin-bottom: 14px;
}
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 14px; }
.stat { text-align: center; }
.num { font-size: 1.7rem; font-weight: 700; }
.num.yellow { color: #ca8a04; }
.num.blue { color: #2563eb; }
.num.green { color: #16a34a; }
.lbl { font-size: 0.82rem; color: var(--ink-2); margin-top: 4px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
</style>
