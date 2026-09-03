<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { apiJson } from '../composables/useCsrf'
import { useTheme } from '../composables/useTheme'

// Fix-P 对照 v1 admin/laboratory_data_analysis.html:两 tab(实验室竞赛贡献度/竞赛×实验室热力图)+年份多选。
// 偏差:年份池取全局 records 年份集合(v1 取该实验室数据年份);热力图复用全局端点(v1 同为全局)。

interface Contribution { competitionId: number; name: string; awardCount: number }
interface Cell { competition: string; lab: string; count: number }

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const labName = ref('')
const activeTab = ref('contrib')
const years = ref<number[]>([])
const yearsPool = ref<number[]>([])
const contribution = ref<Contribution[]>([])
const heatmap = ref<Cell[]>([])

const contribChartEl = ref<HTMLDivElement>()
const heatChartEl = ref<HTMLDivElement>()
const charts: echarts.ECharts[] = []

function theme() {
  const s = getComputedStyle(document.documentElement)
  return {
    ink2: s.getPropertyValue('--ink-2').trim(),
    line: s.getPropertyValue('--line').trim(),
    brand: s.getPropertyValue('--brand').trim(),
  }
}

function makeChart(el: HTMLDivElement | undefined, option: echarts.EChartsOption) {
  if (!el) return
  const c = echarts.init(el)
  c.setOption(option)
  charts.push(c)
}

function disposeCharts() {
  charts.forEach((c) => c.dispose())
  charts.length = 0
}

function renderContrib() {
  disposeCharts()
  const t = theme()
  makeChart(contribChartEl.value, {
    grid: { left: 200, right: 30, top: 10, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', minInterval: 1, axisLabel: { color: t.ink2 }, splitLine: { lineStyle: { color: t.line } } },
    yAxis: {
      type: 'category',
      data: contribution.value.map((c) => c.name),
      axisLabel: { color: t.ink2, width: 180, overflow: 'truncate' },
      axisLine: { lineStyle: { color: t.line } },
    },
    series: [{
      type: 'bar',
      data: contribution.value.map((c) => c.awardCount),
      itemStyle: { color: t.brand, borderRadius: [0, 4, 4, 0] },
    }],
  })
}

function renderHeat() {
  disposeCharts()
  const t = theme()
  const compNames = [...new Set(heatmap.value.map((c) => c.competition))]
  const labNames = [...new Set(heatmap.value.map((c) => c.lab))]
  const data = heatmap.value.map((c) => [compNames.indexOf(c.competition), labNames.indexOf(c.lab), c.count])
  const maxV = Math.max(1, ...heatmap.value.map((c) => c.count))
  makeChart(heatChartEl.value, {
    grid: { left: 200, right: 60, top: 10, bottom: 60 },
    tooltip: { formatter: (p: unknown) => {
      const params = p as { data: [number, number, number] }
      return `${compNames[params.data[0]]} × ${labNames[params.data[1]]}:${params.data[2]}`
    } },
    xAxis: { type: 'category', data: compNames, axisLabel: { color: t.ink2, rotate: 45, width: 120, overflow: 'truncate' }, axisLine: { lineStyle: { color: t.line } } },
    yAxis: { type: 'category', data: labNames, axisLabel: { color: t.ink2 }, axisLine: { lineStyle: { color: t.line } } },
    visualMap: { min: 0, max: maxV, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#eef4ff', t.brand] }, textStyle: { color: t.ink2 } },
    series: [{ type: 'heatmap', data }],
  })
}

function toggleYear(y: number) {
  if (years.value.includes(y)) {
    if (years.value.length > 1) years.value = years.value.filter((x) => x !== y)
  } else {
    years.value = [...years.value, y]
  }
}

async function loadCharts() {
  const qs = new URLSearchParams()
  years.value.forEach((y) => qs.append('years', String(y)))
  const [c, h] = await Promise.all([
    apiJson('GET', `/api/v2/admin/analysis/laboratory/${id}/contribution?${qs}`),
    apiJson('GET', `/api/v2/admin/analysis/heatmap?${qs}`),
  ])
  contribution.value = c.code === 0 ? c.data : []
  heatmap.value = h.code === 0 ? h.data.cells : []
  if (activeTab.value === 'contrib') renderContrib()
  else renderHeat()
}

watch(activeTab, () => {
  if (activeTab.value === 'contrib') renderContrib()
  else renderHeat()
})
// UX-2 挂账小批:主题切换重绘(图色渲染时读 tokens,切换后按当前 tab 重建)
const { theme: themeRef } = useTheme()
watch(themeRef, () => {
  if (activeTab.value === 'contrib') renderContrib()
  else renderHeat()
})

onMounted(async () => {
  const lab = await apiJson('GET', `/api/v2/admin/laboratories/${id}/detail`)
  if (lab.code === 0) labName.value = lab.data.name
  const r = await apiJson('GET', '/api/v2/admin/analysis/records')
  if (r.code === 0) {
    yearsPool.value = [...new Set<number>(r.data.map((x: { year: number }) => x.year))]
      .sort((a: number, b: number) => b - a)
    years.value = [...yearsPool.value]
  }
  await loadCharts()
})

onBeforeUnmount(disposeCharts)
</script>

<template>
  <div>
    <div class="page-head">
      <h1>实验室数据分析{{ labName ? ` - ${labName}` : '' }}</h1>
      <el-button @click="router.push(`/admin/laboratories/${id}`)">
        返回详情
      </el-button>
    </div>

    <div class="c-panel pad mb-3">
      <span class="muted small mr-2">年份:</span>
      <el-check-tag
        :checked="years.length === yearsPool.length"
        size="small"
        @change="years = [...yearsPool]"
      >
        全部
      </el-check-tag>
      <el-check-tag
        v-for="y in yearsPool"
        :key="y"
        size="small"
        :checked="years.includes(y)"
        @change="toggleYear(y)"
      >
        {{ y }}
      </el-check-tag>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane
        label="竞赛贡献度"
        name="contrib"
      >
        <div
          ref="contribChartEl"
          class="chart"
        />
        <el-empty
          v-if="!contribution.length"
          description="该实验室暂无获奖数据"
          :image-size="80"
        />
      </el-tab-pane>
      <el-tab-pane
        label="竞赛×实验室 获奖热力图"
        name="heat"
      >
        <div
          ref="heatChartEl"
          class="chart"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.chart { width: 100%; height: 420px; }
.mb-3 { margin-bottom: 14px; }
.mr-2 { margin-right: 8px; }
.muted { color: var(--ink-2); }
.small { font-size: 0.8rem; }
</style>
