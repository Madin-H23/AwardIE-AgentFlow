<template>
  <ContentWrap>
    <el-alert
      title="导出行数超过上限时会明确报错，不会静默截断"
      type="info"
      :closable="false"
      class="mb-16px"
    />
    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="never" class="export-card">
          <div class="export-title">竞赛年度汇总</div>
          <div class="export-desc">按竞赛 × 年份 × 获奖等级汇总，用于年度统计表</div>
          <el-button type="primary" class="mt-12px" @click="doExport('competition')">
            <Icon icon="ep:download" class="mr-5px" />下载
          </el-button>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="never" class="export-card">
          <div class="export-title">学生获奖明细</div>
          <div class="export-desc">学工台账：学号、姓名、竞赛、获奖等级、年份</div>
          <el-button type="primary" class="mt-12px" @click="doExport('student')">
            <Icon icon="ep:download" class="mr-5px" />下载
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </ContentWrap>

  <ContentWrap>
    <div class="mb-10px text-16px font-600">格式选择</div>
    <el-radio-group v-model="format">
      <el-radio-button value="xlsx">Excel(xlsx)</el-radio-button>
      <el-radio-button value="csv">CSV</el-radio-button>
    </el-radio-group>
    <div class="mt-8px text-12px text-gray-500">
      CSV 带 UTF-8 BOM，Excel 打开中文不乱码
    </div>
  </ContentWrap>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  exportCompetitionSummaryCsv,
  exportCompetitionSummaryXlsx,
  exportStudentAffairsCsv,
  exportStudentAffairsXlsx
} from '@/api/business'
import download from '@/utils/download'

defineOptions({ name: 'Export' })

const message = useMessage()
const format = ref<'xlsx' | 'csv'>('xlsx')

/** CSV 下载:框架 download 对象只有 excel/word/zip/html,CSV 需自己走 blob 下载 */
const download0 = (data: Blob, fileName: string, mimeType: string) => {
  const blob = new Blob([data], { type: mimeType })
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = fileName
  a.click()
  URL.revokeObjectURL(href)
}

const doExport = async (kind: 'competition' | 'student') => {
  try {
    const data =
      kind === 'competition'
        ? format.value === 'csv'
          ? await exportCompetitionSummaryCsv()
          : await exportCompetitionSummaryXlsx()
        : format.value === 'csv'
          ? await exportStudentAffairsCsv()
          : await exportStudentAffairsXlsx()
    const name = kind === 'competition' ? '竞赛年度汇总' : '学生获奖明细'
    // 服务端已带 Content-Disposition 文件名;这里统一由前端命名,避免"无扩展名文件"
    // (v2 的 download 属性缺扩展名会覆盖服务端名字)
    if (format.value === 'xlsx') {
      download.excel(data, `${name}.xlsx`)
    } else {
      download0(data, `${name}.csv`, 'text/csv;charset=UTF-8')
    }
    message.success('导出成功')
  } catch (e) {
    // request.download 已统一弹错误提示,这里只兜底未捕获的情况
    message.error('导出失败')
  }
}
</script>

<style scoped>
.export-card {
  height: 100%;
}
.export-title {
  font-size: 16px;
  font-weight: 600;
}
.export-desc {
  margin-top: 6px;
  min-height: 38px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
