<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { InfoFilled, Medal } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #28:对照 v1 admin/dashboard.html 五区块重做(页面头提示条/资产条4卡/汇总卡/工具条+Top表/趋势卡)
// 口径见 docs/重构二期/03-对照验收/#28-dashboard-对照记录.md

interface Summary {
  totalAwards: number
  awardMgmt: number
  awardTeacher: number
  pendingSubmit: number
  whitelist: number
  competitions: number
}
interface Overview {
  summary: Summary
  category: Record<'award' | 'patent' | 'software' | 'innovation' | 'other', number>
  trend: Array<{ period: string; count: number }>
  compare: { this: number; last: number; deltaPct: number | null }
  byCompetition: Array<{ name: string; total: number }>
}

const data = ref<Overview | null>(null)
const months = ref<number | null>(null) // 周期:6/12/null=全部(v1 periodSelect 同款)
const gran = ref<'month' | 'year'>('month') // 趋势粒度(v1 trendSelect 死选项 → v2 活功能)
const chartEl = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const fmt = (n: number | null | undefined) => (n == null ? '–' : Number(n).toLocaleString())

const grandTotal = computed(() => {
  if (!data.value) return 0
  const c = data.value.category
  return c.award + c.patent + c.software + c.innovation + c.other
})
const density = computed(() =>
  data.value && data.value.summary.competitions ? grandTotal.value / data.value.summary.competitions : 0,
)
const whitelistPct = computed(() => {
  const s = data.value?.summary
  return s && s.competitions ? Math.round((s.whitelist / s.competitions) * 100) : 0
})
const compSum = computed(() =>
  data.value ? data.value.byCompetition.reduce((a, b) => a + b.total, 0) : 0,
)

// 月序列补零(v1 renderTrend 同款;按年不补)
const trendSeries = computed(() => {
  const list = (data.value?.trend ?? []).map((r) => ({ m: r.period, c: r.count }))
  if (!list.length || gran.value === 'year') return list
  const filled: Array<{ m: string; c: number }> = []
  let cur = list[0].m
  while (cur <= list[list.length - 1].m) {
    const hit = list.find((x) => x.m === cur)
    filled.push({ m: cur, c: hit ? hit.c : 0 })
    const [y, mo] = cur.split('-').map(Number)
    cur = mo === 12 ? `${y + 1}-01` : `${y}-${String(mo + 1).padStart(2, '0')}`
  }
  return filled
})

function renderChart() {
  if (!chartEl.value) return
  chart = chart ?? echarts.init(chartEl.value)
  const styles = getComputedStyle(document.documentElement)
  const ink2 = styles.getPropertyValue('--ink-2').trim()
  const line = styles.getPropertyValue('--line').trim()
  const brand = styles.getPropertyValue('--brand').trim()
  chart.setOption({
    grid: { left: 48, right: 20, top: 24, bottom: 30 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: trendSeries.value.map((x) => x.m),
      axisLine: { lineStyle: { color: line } },
      axisLabel: { color: ink2 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: line } },
      axisLabel: { color: ink2 },
    },
    series: [{
      name: '入库数',
      type: 'line',
      smooth: true,
      symbolSize: 7,
      data: trendSeries.value.map((x) => x.c),
      lineStyle: { color: brand, width: 2 },
      itemStyle: { color: brand },
    }],
  })
}

async function load() {
  const qs = new URLSearchParams()
  if (months.value) qs.set('months', String(months.value))
  qs.set('gran', gran.value)
  const body = await apiJson('GET', `/api/v2/admin/stats/overview?${qs}`)
  if (body.code === 0) {
    data.value = body.data
    renderChart()
  }
}

watch(gran, () => {
  chart?.dispose()
  chart = null
  load()
})
watch(months, load)

const onResize = () => chart?.resize()
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<template>
  <div class="dash-page">
    <!-- ① 页面头 + 提示条 -->
    <h1>成果数据总览</h1>
    <div class="page-alert">
      <el-icon><InfoFilled /></el-icon>
      <span>数据实时统计;成果分类以奖状/专利/软著/其他四类统计,最终口径以人工审核归档数据为准。</span>
    </div>

    <!-- ② 资产条 4 卡 -->
    <div class="vitals">
      <div class="vital-card">
        <div class="vital-label">
          <el-icon><Medal /></el-icon>成果总数
        </div>
        <div class="vital-value mono-data">
          {{ fmt(grandTotal) }}
        </div>
        <div class="vital-sub">
          奖状 {{ data?.category.award ?? 0 }} · 专利 {{ data?.category.patent ?? 0 }} · 软著 {{ data?.category.software ?? 0 }} · 大创 {{ data?.category.innovation ?? 0 }} · 其他 {{ data?.category.other ?? 0 }}
        </div>
      </div>
      <div class="vital-card">
        <div class="vital-label">
          <span
            class="pulse-dot"
            :class="{ down: (data?.summary.pendingSubmit ?? 0) > 0 }"
          />待审核
        </div>
        <div
          class="vital-value mono-data"
          :class="{ alarming: (data?.summary.pendingSubmit ?? 0) > 0 }"
        >
          {{ fmt(data?.summary.pendingSubmit) }}
        </div>
        <div class="vital-sub">
          {{ (data?.summary.pendingSubmit ?? 0) > 0 ? '需人工处理' : '无积压' }}
        </div>
      </div>
      <div class="vital-card">
        <div class="vital-label">
          <el-icon><Medal /></el-icon>白名单竞赛
        </div>
        <div class="vital-value mono-data">
          {{ fmt(data?.summary.whitelist) }}
        </div>
        <div class="vital-sub">
          占 {{ whitelistPct }}% 竞赛
        </div>
      </div>
      <div class="vital-card">
        <div class="vital-label">
          <el-icon><InfoFilled /></el-icon>成果·竞赛密度
        </div>
        <div class="vital-value mono-data">
          {{ density.toFixed(1) }}
        </div>
        <div class="vital-sub">
          共 {{ data?.summary.competitions ?? 0 }} 个竞赛
        </div>
      </div>
    </div>

    <!-- ③ 汇总卡:左大数字 + 右分类计数/公式行/口径注脚 -->
    <div class="c-panel pay-panel">
      <div class="pay-total">
        <div class="label">
          本周期成果新增(2026 年至今)
        </div>
        <div class="num mono-data">
          {{ fmt(grandTotal) }}
        </div>
        <div class="sub">
          待审核 {{ data?.summary.pendingSubmit ?? 0 }} · 白名单竞赛 {{ data?.summary.whitelist ?? 0 }}<br>
          本月新增 {{ data?.compare.this ?? 0 }} · 上月 {{ data?.compare.last ?? 0 }}
          <template v-if="data?.compare.deltaPct != null">
            · 环比 <span :class="data.compare.deltaPct >= 0 ? 'delta-up' : 'delta-down'">{{ data.compare.deltaPct >= 0 ? '▲' : '▼' }}{{ Math.abs(data.compare.deltaPct) }}%</span>
          </template>
        </div>
      </div>
      <div class="pay-detail">
        <div class="label">
          分类计数
        </div>
        <div class="pay-items">
          <div class="item">
            <span class="k">奖状 (awards)</span><span class="v">{{ fmt(data?.category.award) }}</span>
          </div>
          <div class="item">
            <span class="k">专利 (patents)</span><span class="v">{{ fmt(data?.category.patent) }}</span>
          </div>
          <div class="item">
            <span class="k">软著 (software)</span><span class="v">{{ fmt(data?.category.software) }}</span>
          </div>
          <div class="item">
            <span class="k">大创 (innovation)</span><span class="v">{{ fmt(data?.category.innovation) }}</span>
          </div>
          <div class="item">
            <span class="k">其他文件 (other)</span><span class="v">{{ fmt(data?.category.other) }}</span>
          </div>
        </div>
        <div class="pay-formula">
          新增 = 奖状 + 专利 + 软著 + 大创 + 其他
        </div>
        <div class="pay-note">
          奖状口径:全量 {{ fmt(data?.summary.totalAwards) }}(其中教师证书 {{ fmt(data?.summary.awardTeacher) }};管理/学生视角 {{ fmt(data?.summary.awardMgmt) }})
        </div>
      </div>
    </div>

    <!-- ④ 工具条 + 竞赛战果 Top -->
    <div class="c-panel">
      <div class="filter-bar topbar">
        <span class="fb-label">周期</span>
        <el-select
          v-model="months"
          placeholder="全部"
          style="width: 110px"
          data-testid="dash-period"
        >
          <el-option
            label="近 6 月"
            :value="6"
          />
          <el-option
            label="近 12 月"
            :value="12"
          />
          <el-option
            label="全部"
            :value="null"
          />
        </el-select>
        <span class="spacer" />
        <el-tooltip
          content="数据导出纵切面待接入 v2"
          placement="top"
        >
          <span>
            <el-button
              :icon="undefined"
              disabled
            >
              导出
            </el-button>
          </span>
        </el-tooltip>
      </div>
      <div class="panel-body">
        <div class="panel-head">
          <span>竞赛战果 Top</span>
          <span class="muted">按获奖总数排序</span>
        </div>
        <el-table
          :data="data?.byCompetition ?? []"
          size="small"
        >
          <el-table-column
            prop="name"
            label="竞赛"
            min-width="260"
          />
          <el-table-column
            label="获奖总数"
            width="120"
            align="right"
          >
            <template #default="scope">
              <span class="mono-data">{{ fmt(scope.row.total) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="占比"
            width="220"
          >
            <template #default="scope">
              <div class="bar-wrap">
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :style="{ width: compSum ? (scope.row.total / compSum * 100).toFixed(1) + '%' : '0' }"
                  />
                </div>
                <span class="pct mono-data">{{ compSum ? (scope.row.total / compSum * 100).toFixed(1) : '0' }}%</span>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ⑤ 趋势卡 -->
    <div class="c-panel">
      <div class="panel-head pad">
        <span>成果入库趋势</span>
        <el-select
          v-model="gran"
          style="width: 110px"
          data-testid="dash-gran"
        >
          <el-option
            label="按月汇总"
            value="month"
          />
          <el-option
            label="按年度"
            value="year"
          />
        </el-select>
      </div>
      <div class="panel-body">
        <div
          ref="chartEl"
          style="height: 320px"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 五区块样式对照 v1 dashboard.html 内联样式 + console_tokens.css 生命体征带/筛选栏 */
.dash-page { }
h1 { font-size: 1.35rem; font-weight: 600; color: var(--ink); margin: 0 0 8px; }

.page-alert {
  display: flex; align-items: center; gap: 8px;
  background: color-mix(in srgb, var(--brand) 6%, var(--panel));
  border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 14px; font-size: 0.82rem; color: var(--ink-2);
}
.page-alert .el-icon { color: var(--brand); }

.vitals { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 16px 0; }
.vital-card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.vital-label { font-size: 0.78rem; color: var(--ink-2); display: flex; align-items: center; gap: 6px; }
.vital-value { font-size: 1.7rem; font-weight: 700; }
.vital-sub { font-size: 0.74rem; color: var(--ink-2); }
.pulse-dot {
  width: 9px; height: 9px; border-radius: 50%; background: var(--ok); display: inline-block;
  animation: breathe 2.6s ease-in-out infinite;
}
.pulse-dot.down { background: var(--sev-error); animation-duration: 0.9s; }
.vital-value.alarming { color: var(--sev-error); animation: pulse 1.2s ease-in-out infinite; }
@keyframes breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.45); }
  50% { box-shadow: 0 0 0 6px rgba(15, 118, 110, 0); }
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }

.c-panel {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  margin-bottom: 16px;
}
.pay-panel { display: grid; grid-template-columns: 1fr 2fr; gap: 16px; padding: 16px; }
.pay-total { border-right: 1px solid var(--line); padding-right: 16px; }
.pay-total .label, .pay-detail > .label { font-size: 0.8rem; color: var(--ink-2); margin-bottom: 6px; }
.pay-total .num { font-size: 2.6rem; font-weight: 700; line-height: 1; }
.pay-total .sub { font-size: 0.74rem; color: var(--ink-2); margin-top: 8px; line-height: 1.7; }
.delta-up { color: var(--ok); }
.delta-down { color: var(--sev-error); }
.pay-items { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 28px; }
.pay-items .item {
  display: flex; justify-content: space-between; align-items: baseline;
  padding-bottom: 8px; border-bottom: 1px dashed var(--line);
}
.pay-items .k { color: var(--ink-2); font-size: 0.85rem; }
.pay-items .v { font-variant-numeric: tabular-nums; }
.pay-formula { font-size: 0.75rem; color: var(--ink-2); margin-top: 14px; }
.pay-note { font-size: 0.74rem; color: var(--ink-2); margin-top: 6px; }

.filter-bar {
  background: color-mix(in srgb, var(--ink) 4%, var(--panel));
  border-bottom: 1px solid var(--line); border-radius: 8px 8px 0 0;
  padding: 10px 14px; display: flex; align-items: center; gap: 10px;
}
.filter-bar .fb-label { color: var(--ink-2); font-size: 0.82rem; }
.filter-bar .spacer { margin-left: auto; }
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  font-weight: 600; font-size: 0.95rem; color: var(--ink);
}
.panel-head .muted { font-weight: 400; font-size: 0.78rem; color: var(--ink-2); }
.panel-head.pad { padding: 12px 14px; }
.panel-body { padding: 12px 14px; }

.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar-track { flex: 1; height: 5px; border-radius: 3px; background: var(--line); position: relative; overflow: hidden; }
.bar-fill { position: absolute; inset: 0 auto 0 0; border-radius: 3px; background: var(--brand); }
.pct { font-size: 0.78rem; color: var(--ink-2); width: 48px; text-align: right; }
</style>
