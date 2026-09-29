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

  <ContentWrap v-if="teachers.length > 0">
    <div class="mb-10px flex items-center justify-between">
      <span class="text-16px font-600">教师维度</span>
      <span class="text-12px text-gray-500">按指导教师名单精确匹配,同名教师以编号区分(如张三1/张三2)</span>
    </div>
    <el-table :data="teachers" border empty-text="暂无数据">
      <el-table-column type="index" label="#" width="60" align="center" />
      <el-table-column label="教师" prop="name" min-width="140" />
      <el-table-column label="指导获奖" prop="supervised" min-width="100" align="right" />
      <el-table-column label="本人教师证书" prop="ownAwards" min-width="120" align="right" />
    </el-table>
  </ContentWrap>

  <ContentWrap v-if="Object.keys(laboratory).length > 0">
    <div class="mb-10px text-16px font-600">实验室获奖分布</div>
    <el-table :data="laboratoryRows" border empty-text="暂无数据">
      <el-table-column label="实验室" prop="label" min-width="200" />
      <el-table-column label="获奖数" prop="value" min-width="100" align="right" />
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
import { getStatsByCompetition, getStatsByLaboratory, getStatsByTeacher, getStatsOverview } from '@/api/business'

defineOptions({ name: 'Stats' })

const loading = ref(false)
const summary = ref<any>({})
const category = ref<Record<string, number>>({})
const ranking = ref<any[]>([])
const laboratory = ref<Record<string, number>>({})
const teachers = ref<any[]>([])

const LAB_LABELS: Record<string, string> = {
  未归属: '未归属实验室'
}

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

const laboratoryRows = computed(() =>
  Object.entries(laboratory.value).map(([name, value]) => ({
    label: LAB_LABELS[name] || name,
    value
  }))
)

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
    const [overview, top, laboratoryData, teacherRows] = await Promise.all([
      getStatsOverview(),
      getStatsByCompetition(),
      getStatsByLaboratory().catch(() => ({})),
      getStatsByTeacher().catch(() => [])
    ])
    // overview 是整个响应体 {summary, category} —— 汇总卡要绑定它的 summary 子对象。
    // 批14 前实测写成了 summary.value = overview,五张卡全部绑在错误层级上恒 0,
    // 而分类表(category 绑对了)有数,对比之下才暴露。
    summary.value = overview?.summary || {}
    category.value = overview?.category || {}
    ranking.value = top || []
    laboratory.value = laboratoryData || {}
    teachers.value = teacherRows || []
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
