<script setup lang="ts">
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// #31 对照 v1 admin/data_export/main.html:三 tab(系年度总结/学生事务/教师个人)。
// 格式偏差:CSV 起步(v1 xlsx 模板报告挂账),见对照记录。附件下载统一 a 标签直连(GET)。
const year = ref<number | null>(new Date().getFullYear())
const dateRange = ref<[string, string] | null>(null)
const format = ref<'xlsx' | 'csv'>('xlsx') // #41:xlsx 默认,csv 次选

function downloadDirect(endpoint: string, name: string) {
  const a = document.createElement('a')
  a.href = endpoint
  a.download = name
  a.click()
  ElMessage.success('已开始下载')
}

function exportSummary() {
  const qs = new URLSearchParams()
  if (year.value) qs.set('year', String(year.value))
  const ext = format.value
  downloadDirect(`/api/v2/admin/export/department-summary.${ext}?${qs}`, 'department-summary')
}

function exportTab(endpointBase: string) {
  downloadDirect(`/api/v2/admin/export/${endpointBase}.${format.value}`, endpointBase)
}
</script>

<template>
  <div>
    <div class="page-head">
      <h1>数据导出</h1>
    </div>

    <el-tabs model-value="summary">
      <el-tab-pane
        label="系年度总结"
        name="summary"
      >
        <div class="c-panel pad">
          <div class="form-row">
            <span class="label">年份</span>
            <el-input-number
              v-model="year"
              :min="2000"
              :max="2100"
              controls-position="right"
              style="width: 130px"
            />
            <span class="label">格式</span>
            <el-radio-group v-model="format">
              <el-radio-button value="xlsx">
                xlsx(带样式)
              </el-radio-button>
              <el-radio-button value="csv">
                CSV
              </el-radio-button>
            </el-radio-group>
            <el-button
              type="primary"
              :icon="Download"
              data-testid="export-summary"
              @click="exportSummary"
            >
              导出
            </el-button>
          </div>
          <p class="hint">
            按竞赛×年份×获奖等级汇总获奖数量;xlsx 为带样式多 sheet 报告(汇总+明细),CSV 为次选格式。
          </p>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="学生事务"
        name="student"
      >
        <div class="c-panel pad">
          <p class="hint">
            导出全部学生获奖明细(学号/姓名/竞赛/获奖等级/年份)。
          </p>
          <el-button
            type="primary"
            :icon="Download"
            @click="exportTab('student-affairs')"
          >
            导出
          </el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="教师个人"
        name="teacher"
      >
        <div class="c-panel pad">
          <p class="hint">
            导出教师指导获奖明细(工号/姓名/竞赛/获奖等级/年份)。
          </p>
          <el-button
            type="primary"
            :icon="Download"
            @click="exportTab('teacher-personal')"
          >
            导出
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.form-row .label { font-size: 0.85rem; color: var(--ink-2); }
.hint {
  font-size: 0.8rem;
  color: var(--ink-2);
  margin: 0 0 12px;
}
</style>
