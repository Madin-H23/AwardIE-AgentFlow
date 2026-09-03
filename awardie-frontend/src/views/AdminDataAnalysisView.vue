<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { apiJson } from '../composables/useCsrf'
import { useTheme } from '../composables/useTheme'

// #30 对照 v1 admin/data_analysis.html:三 tab(竞赛信息/竞赛分析/获奖数据分析)。
// 偏差:Tab1 时间线图为获奖体量条形(v1 三时间点解析器不移植),详见对照记录。

interface Comp {
  id: number
  name: string
  timeRaw: string | null
  website: string
  whiteList: boolean
  awardCount: number
}
interface Contribution {
  competitionId: number
  name: string
  awardCount: number
}
interface Cell {
  competition: string
  lab: string
  count: number
}
interface Record_ {
  year: number
  lab: string
  competition: string
  level: string | null
  granted_role: string | null
}

const activeTab = ref('tab1')
const comps = ref<Comp[]>([])
const years = ref<number[]>([])
const yearsPool = ref<number[]>([])
const whiteListOnly = ref(false)
const includeTeacher = ref(false)
const contribution = ref<Contribution[]>([])
const heatmap = ref<Cell[]>([])
const records = ref<Record_[]>([])
const xAxisBy = ref<'year' | 'laboratory'>('year')
const colorBy = ref<'laboratory' | 'year' | 'competition_level'>('laboratory')
const chartType = ref<'grouped_bar' | 'line' | 'donut'>('grouped_bar')

const t1ChartEl = ref<HTMLDivElement>()
const contribChartEl = ref<HTMLDivElement>()
const heatChartEl = ref<HTMLDivElement>()
const dynChartEl = ref<HTMLDivElement>()
const charts: echarts.ECharts[] = []

function theme() {
  const s = getComputedStyle(document.documentElement)
  return {
    ink: s.getPropertyValue('--ink').trim(),
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

// Tab1:竞赛获奖体量条形(v1 时间点散点的降维,见对照记录)
function renderTab1() {
  disposeCharts()
  const t = theme()
  const sorted = [...comps.value].sort((a, b) => b.awardCount - a.awardCount).slice(0, 15)
  makeChart(t1ChartEl.value, {
    grid: { left: 200, right: 30, top: 10, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', minInterval: 1, axisLabel: { color: t.ink2 }, splitLine: { lineStyle: { color: t.line } } },
    yAxis: { type: 'category', data: sorted.map((c) => c.name), axisLabel: { color: t.ink2, width: 180, overflow: 'truncate' }, axisLine: { lineStyle: { color: t.line } } },
    series: [{ type: 'bar', data: sorted.map((c) => c.awardCount), itemStyle: { color: t.brand, borderRadius: [0, 4, 4, 0] } }],
  })
}

// Tab2:贡献度+热力图
function renderTab2() {
  disposeCharts()
  const t = theme()
  makeChart(contribChartEl.value, {
    grid: { left: 200, right: 30, top: 10, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', minInterval: 1, axisLabel: { color: t.ink2 }, splitLine: { lineStyle: { color: t.line } } },
    yAxis: { type: 'category', data: contribution.value.slice(0, 20).map((c) => c.name), axisLabel: { color: t.ink2, width: 180, overflow: 'truncate' }, axisLine: { lineStyle: { color: t.line } } },
    series: [{ type: 'bar', data: contribution.value.slice(0, 20).map((c) => c.awardCount), itemStyle: { color: t.brand, borderRadius: [0, 4, 4, 0] } }],
  })

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

// Tab3:前端聚合(对照 v1 动态图:X 轴/颜色分组/图表类型)
const dynAgg = computed(() => {
  const catKey = (r: Record_) => (xAxisBy.value === 'year' ? String(r.year) : r.lab)
  const grpKey = (r: Record_) =>
    colorBy.value === 'laboratory' ? r.lab : colorBy.value === 'year' ? String(r.year) : (r.level || '未分级')
  const groups = new Map<string, Map<string, number>>()
  for (const r of records.value) {
    const cat = catKey(r)
    const grp = grpKey(r)
    if (!groups.has(cat)) groups.set(cat, new Map())
    const m = groups.get(cat)!
    m.set(grp, (m.get(grp) ?? 0) + 1)
  }
  const cats = [...groups.keys()].sort()
  const seriesNames = [...new Set(records.value.map(grpKey))].sort()
  const series = seriesNames.map((name) => ({
    name,
    type: chartType.value === 'line' ? 'line' : 'bar',
    data: cats.map((c) => groups.get(c)?.get(name) ?? 0),
  }))
  return { cats, seriesNames, series }
})

function renderTab3() {
  disposeCharts()
  const t = theme()
  if (chartType.value === 'donut') {
    const data = dynAgg.value.seriesNames.map((n) => ({
      name: n,
      value: (dynAgg.value.series.find((s) => s.name === n)?.data as number[]).reduce((a: number, b: number) => a + b, 0),
    }))
    makeChart(dynChartEl.value, {
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', left: 'left', textStyle: { color: t.ink2 } },
      series: [{ type: 'pie', radius: ['40%', '70%'], data, itemStyle: { borderRadius: 6 } }],
    })
    return
  }
  makeChart(dynChartEl.value, {
    grid: { left: 60, right: 30, top: 50, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { data: dynAgg.value.seriesNames, textStyle: { color: t.ink2 } },
    xAxis: { type: 'category', data: dynAgg.value.cats, axisLabel: { color: t.ink2 }, axisLine: { lineStyle: { color: t.line } } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: t.ink2 }, splitLine: { lineStyle: { color: t.line } } },
    series: dynAgg.value.series as echarts.SeriesOption[],
  })
}

async function loadBase() {
  const c = await apiJson('GET', '/api/v2/admin/analysis/competitions')
  if (c.code === 0) comps.value = c.data
  const r = await apiJson('GET', '/api/v2/admin/analysis/records')
  if (r.code === 0) {
    records.value = r.data
    yearsPool.value = [...new Set<number>(r.data.map((x: Record_) => x.year))].sort((a: number, b: number) => b - a)
  }
}

async function loadTab2() {
  const qs = new URLSearchParams()
  if (years.value.length) years.value.forEach((y) => qs.append('years', String(y)))
  if (whiteListOnly.value) qs.set('whiteListOnly', 'true')
  if (includeTeacher.value) qs.set('includeTeacher', 'true')
  const [c, h] = await Promise.all([
    apiJson('GET', `/api/v2/admin/analysis/contribution?${qs}`),
    apiJson('GET', `/api/v2/admin/analysis/heatmap?${qs}`),
  ])
  if (c.code === 0) contribution.value = c.data
  if (h.code === 0) heatmap.value = h.data.cells
  renderTab2()
}

watch(activeTab, (tab) => {
  if (tab === 'tab2') loadTab2()
  else if (tab === 'tab3') renderTab3()
})
watch([xAxisBy, colorBy, chartType], () => {
  if (activeTab.value === 'tab3') renderTab3()
})
// UX-2 挂账小批:主题切换重绘(图色渲染时读 tokens,切换后按当前 tab 重建)
const { theme: themeRef } = useTheme()
watch(themeRef, () => {
  if (activeTab.value === 'tab2') loadTab2()
  else if (activeTab.value === 'tab3') renderTab3()
  else renderTab1()
})

const onResize = () => charts.forEach((c) => c.resize())
onMounted(async () => {
  await loadBase()
  renderTab1()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<template>
  <div>
    <div class="page-head">
      <h1>数据分析与导出</h1>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Tab1 竞赛信息 -->
      <el-tab-pane
        label="竞赛信息"
        name="tab1"
      >
        <div
          class="c-panel pad"
          style="margin-bottom: 14px"
        >
          <h3 class="blk-title">
            竞赛获奖体量(前 15)
          </h3>
          <div
            ref="t1ChartEl"
            style="height: 400px"
          />
        </div>
        <div class="c-panel pad">
          <el-table
            :data="comps"
            size="small"
          >
            <el-table-column
              prop="name"
              label="竞赛名称"
              min-width="260"
            />
            <el-table-column
              label="时间范围"
              width="150"
            >
              <template #default="scope">
                {{ scope.row.timeRaw || '-' }}
              </template>
            </el-table-column>
            <el-table-column
              label="官网"
              min-width="180"
            >
              <template #default="scope">
                <span class="muted">{{ scope.row.website }}</span>
              </template>
            </el-table-column>
            <el-table-column
              label="白名单"
              width="90"
            >
              <template #default="scope">
                <el-tag
                  :type="scope.row.whiteList ? 'success' : 'info'"
                  size="small"
                >
                  {{ scope.row.whiteList ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="awardCount"
              label="获奖数"
              width="90"
              align="right"
            />
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Tab2 竞赛分析 -->
      <el-tab-pane
        label="竞赛分析"
        name="tab2"
        lazy
      >
        <div class="c-panel pad filter-panel">
          <span class="label">年份筛选</span>
          <div class="year-tags">
            <el-check-tag
              v-for="y in yearsPool"
              :key="y"
              :checked="years.includes(y)"
              @change="years.includes(y) ? years.splice(years.indexOf(y), 1) : years.push(y)"
            >
              {{ y }}
            </el-check-tag>
          </div>
          <el-checkbox v-model="whiteListOnly">
            仅白名单赛事
          </el-checkbox>
          <el-checkbox v-model="includeTeacher">
            包含教师证书
          </el-checkbox>
          <el-button
            type="primary"
            style="margin-left: auto"
            @click="loadTab2"
          >
            更新
          </el-button>
        </div>
        <div
          class="c-panel pad"
          style="margin-bottom: 14px"
        >
          <h3 class="blk-title">
            竞赛贡献度
          </h3>
          <div
            ref="contribChartEl"
            style="height: 500px"
          />
        </div>
        <div class="c-panel pad">
          <h3 class="blk-title">
            竞赛×实验室 获奖数量热力图
          </h3>
          <div
            ref="heatChartEl"
            style="height: 650px"
          />
        </div>
      </el-tab-pane>

      <!-- Tab3 获奖数据分析 -->
      <el-tab-pane
        label="获奖数据分析"
        name="tab3"
        lazy
      >
        <el-row :gutter="14">
          <el-col :span="6">
            <div class="c-panel pad">
              <h3 class="blk-title">
                图表设置
              </h3>
              <div class="field">
                <div class="label">
                  X 轴
                </div>
                <el-select
                  v-model="xAxisBy"
                  style="width: 100%"
                >
                  <el-option
                    label="年份"
                    value="year"
                  />
                  <el-option
                    label="实验室"
                    value="laboratory"
                  />
                </el-select>
              </div>
              <div class="field">
                <div class="label">
                  颜色分组
                </div>
                <el-select
                  v-model="colorBy"
                  style="width: 100%"
                >
                  <el-option
                    label="实验室"
                    value="laboratory"
                  />
                  <el-option
                    label="年份"
                    value="year"
                  />
                  <el-option
                    label="竞赛等级"
                    value="competition_level"
                  />
                </el-select>
              </div>
              <div class="field">
                <div class="label">
                  图表类型
                </div>
                <el-select
                  v-model="chartType"
                  style="width: 100%"
                >
                  <el-option
                    label="分组柱状图"
                    value="grouped_bar"
                  />
                  <el-option
                    label="折线图"
                    value="line"
                  />
                  <el-option
                    label="甜甜圈图"
                    value="donut"
                  />
                </el-select>
              </div>
            </div>
          </el-col>
          <el-col :span="18">
            <div class="c-panel pad">
              <div
                ref="dynChartEl"
                style="height: 720px"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.blk-title { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.filter-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.filter-panel .label { font-size: 0.85rem; color: var(--ink-2); }
.year-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.field { margin-bottom: 14px; }
.field .label { font-size: 0.85rem; color: var(--ink-2); margin-bottom: 6px; }
.muted { color: var(--ink-2); font-size: 0.8rem; }
</style>
