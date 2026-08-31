<script setup lang="ts">
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// #31 对照 v1 admin/data_export/main.html:三 tab(系年度总结/学生事务/教师个人)。
// 格式偏差:CSV 起步(v1 xlsx 模板报告挂账),见对照记录。附件下载统一 a 标签直连(GET)。
const year = ref<number | null>(new Date().getFullYear())
const dateRange = ref<[string, string] | null>(null)

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
  downloadDirect(`/api/v2/admin/export/department-summary.csv?${qs}`, 'department-summary')
}
</script>

<template>
  <div>
    <div class="page-head">
      <h1>数据导出</h1>
    </div>

    <el-tabs model-value="summary">
      <el-tab-pane label="系年度总结" name="summary">
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
            <span class="label">起止日期(预留)</span>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始"
              end-placeholder="结束"
              disabled
            />
            <el-button
              type="primary"
              :icon="Download"
              data-testid="export-summary"
              @click="exportSummary"
            >
              导出 CSV
            </el-button>
          </div>
          <p class="hint">
            按竞赛×年份×获奖等级汇总获奖数量;xlsx 模板化报告(含图片打包)按批次迁移中,当前提供 CSV(Excel 可直开)。
          </p>
        </div>
      </el-tab-pane>

      <el-tab-pane label="学生事务" name="student">
        <div class="c-panel pad">
          <p class="hint">
            导出全部学生获奖明细(学号/姓名/竞赛/获奖等级/年份)。
          </p>
          <el-button
            type="primary"
            :icon="Download"
            @click="downloadDirect('/api/v2/admin/export/student-affairs.csv', 'student-affairs')"
          >
            导出 CSV
          </el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="教师个人" name="teacher">
        <div class="c-panel pad">
          <p class="hint">
            导出教师指导获奖明细(工号/姓名/竞赛/获奖等级/年份)。
          </p>
          <el-button
            type="primary"
            :icon="Download"
            @click="downloadDirect('/api/v2/admin/export/teacher-personal.csv', 'teacher-personal')"
          >
            导出 CSV
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
