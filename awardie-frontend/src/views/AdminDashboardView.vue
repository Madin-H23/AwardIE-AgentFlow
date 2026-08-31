<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { apiJson } from '../composables/useCsrf'

const awardsTotal = ref(0)
const pendingTotal = ref(0)
const usersTotal = ref(0)
const competitionsTotal = ref(0)
const chartEl = ref<HTMLDivElement>()

onMounted(async () => {
  const body = await apiJson('GET', '/api/v2/admin/stats')
  if (body.code !== 0) return
  awardsTotal.value = body.data.awardsTotal
  pendingTotal.value = body.data.pendingTotal
  usersTotal.value = body.data.usersTotal
  competitionsTotal.value = body.data.competitionsTotal
  if (chartEl.value) {
    const chart = echarts.init(chartEl.value)
    const trend = body.data.trend as Array<{ month: string; count: number }>
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: trend.map((t) => t.month) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ name: '月度入库', type: 'line', data: trend.map((t) => t.count), smooth: true }],
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
    })
  }
})
</script>

<template>
  <div class="dash-page">
    <el-row :gutter="12">
      <el-col :span="6">
        <el-card>
          <div class="num">
            {{ awardsTotal }}
          </div><div class="lbl">
            成果总数
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="num">
            {{ pendingTotal }}
          </div><div class="lbl">
            待审数
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="num">
            {{ usersTotal }}
          </div><div class="lbl">
            用户数
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="num">
            {{ competitionsTotal }}
          </div><div class="lbl">
            竞赛数
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-top: 12px">
      <h2>月度入库趋势</h2>
      <div
        ref="chartEl"
        style="height: 320px"
      />
    </el-card>
  </div>
</template>

<style scoped>
.dash-page { max-width: 1100px; margin: 24px auto; }
.num { font-size: 32px; font-weight: 600; color: var(--ink); }
.lbl { color: var(--ink-2); font-size: 13px; }
h2 { margin-top: 0; color: var(--ink); }
</style>
