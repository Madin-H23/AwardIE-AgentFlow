<script setup lang="ts">
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// Goal D 对照 v1 teacher/data_export.html(173 行):筛选条件+导出报表(教师关联成果 CSV)。
const year = ref('')

function exportCsv() {
  const qs = new URLSearchParams()
  if (year.value) qs.set('year', year.value)
  const a = document.createElement('a')
  a.href = `/api/v2/teacher/portal/export.csv?${qs}`
  a.download = 'teacher-achievements.csv'
  a.click()
  ElMessage.success('已开始下载')
}
</script>

<template>
  <div>
    <h1 class="title">
      数据导出
    </h1>
    <p class="sub">
      导出您关联的所有竞赛成果数据
    </p>

    <div class="card">
      <h3 class="blk-title">
        筛选条件
      </h3>
      <div class="form-row">
        <span class="label">年份</span>
        <el-input
          v-model="year"
          placeholder="如 2025(留空=全部)"
          style="width: 160px"
          clearable
        />
      </div>
    </div>

    <div class="card">
      <h3 class="blk-title">
        导出报表
      </h3>
      <p class="hint">
        导出本人指导/获奖的成果明细(竞赛/获奖等级/年份/获奖人),CSV 格式,Excel 可直开。
      </p>
      <el-button
        type="primary"
        :icon="Download"
        data-testid="teacher-export-submit"
        @click="exportCsv"
      >
        导出报表
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.title { font-size: 1.35rem; font-weight: 700; color: var(--ink); margin: 0 0 4px; }
.sub { font-size: 0.85rem; color: var(--ink-2); margin: 0 0 16px; }
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 16px; margin-bottom: 14px;
}
.blk-title { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.form-row { display: flex; align-items: center; gap: 10px; }
.label { font-size: 0.85rem; color: var(--ink-2); }
.hint { font-size: 0.8rem; color: var(--ink-2); margin: 0 0 12px; line-height: 1.7; }
</style>
