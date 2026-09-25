<template>
  <ContentWrap>
    <div class="stats-cards">
      <el-card v-for="item in summaryCards" :key="item.label" shadow="never" class="stat-card">
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-label">{{ item.label }}</div>
      </el-card>
    </div>
  </ContentWrap>

  <ContentWrap v-if="categoryRows.length > 0">
    <el-table :data="categoryRows" border>
      <el-table-column label="成果类别" prop="label" min-width="160" />
      <el-table-column label="数量" prop="value" min-width="120" align="right" />
    </el-table>
  </ContentWrap>

  <ContentWrap>
    <div class="mb-10px flex items-center justify-between">
      <span class="text-16px font-600">竞赛战果 Top12</span>
      <el-button :loading="loading" @click="loadData">
        <Icon icon="ep:refresh" class="mr-5px" />刷新
      </el-button>
    </div>
    <el-table :data="ranking" v-loading="loading" border empty-text="暂无数据">
      <el-table-column type="index" label="排名" width="80" align="center" />
      <el-table-column label="竞赛" prop="name" min-width="240" show-overflow-tooltip />
      <el-table-column label="成果数" prop="total" min-width="120" align="right" />
    </el-table>
  </ContentWrap>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getStatsByCompetition, getStatsOverview } from '@/api/business'

defineOptions({ name: 'StatsIndex' })

const loading = ref(false)
const summary = ref<any>({})
const category = ref<Record<string, number>>({})
const ranking = ref<any[]>([])

/** 五类成果的中文标签(顺序与后端 category 返回一致) */
const CATEGORY_LABELS: Array<[string, string]> = [
  ['award', '奖状'],
  ['patent', '专利'],
  ['software', '软著'],
  ['innovation', '大创'],
  ['other', '其他文件']
]

const CATEGORY_TONES: Record<string, string> = {
  award: 'primary',
  patent: 'success',
  software: 'warning',
  innovation: 'info',
  other: 'danger'
}

const summaryCards = computed(() => [
  { label: '成果总数', value: summary.value.awardsTotal ?? 0 },
  { label: '待审核', value: summary.value.pendingSubmit ?? 0 },
  { label: '用户数', value: summary.value.usersTotal ?? 0 },
  { label: '竞赛数', value: summary.value.competitionsTotal ?? 0 },
  { label: '白名单竞赛', value: summary.value.whitelist ?? 0 }
])

const categoryRows = computed(() =>
  CATEGORY_LABELS.map(([key, label]) => ({
    label,
    value: category.value[key] ?? 0,
    type: CATEGORY_TONES[key]
  }))
)

const loadData = async () => {
  loading.value = true
  try {
    const [overview, top] = await Promise.all([getStatsOverview(), getStatsByCompetition()])
    summary.value = overview || {}
    category.value = overview?.category || {}
    ranking.value = top || []
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
