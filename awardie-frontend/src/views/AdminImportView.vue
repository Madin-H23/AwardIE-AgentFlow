<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// #34 对照 v1 file_import/upload.html+results_console.html:
// 上传→解析预览(行级校验)→确认导入→结果控制台。范围声明:大创 xlsx 通道(图片 OCR 批量导入挂账)。
interface Row {
  rowNo: number
  projectNo: string
  projectName: string
  projectType: string
  startDate: string
  endDate: string
  leaderName: string
  leaderId: string
  otherMembers: string
  supervisors: string
  funding: number | null
  error: string | null
}
const rows = ref<Row[]>([])
const sha = ref('')
const fileName = ref('')
const result = ref<{ imported: number; skipped: number; errors: string[] } | null>(null)
const busy = ref(false)

async function onFileChange(file: File) {
  rows.value = []
  result.value = null
  fileName.value = file.name
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const resp = await fetch('/api/v2/admin/import/innovation/preview', {
      method: 'POST', body: fd, credentials: 'include',
    })
    const body = await resp.json()
    if (body.code === 0) {
      rows.value = body.data.rows
      sha.value = body.data.sha256
      ElMessage.success(`解析 ${rows.value.length} 行`)
    } else {
      ElMessage.error(body.message)
    }
  } finally {
    busy.value = false
  }
}

async function confirmImport() {
  busy.value = true
  try {
    const body = await apiJson('POST', '/api/v2/admin/import/innovation/confirm', {
      sha256: sha.value, rows: rows.value,
    })
    if (body.code === 0) {
      result.value = body.data
      ElMessage.success(`导入 ${body.data.imported} 行`)
    } else {
      ElMessage.error(body.message)
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-head">
      <h1>成果/文件导入</h1>
    </div>

    <div class="c-panel pad" style="margin-bottom: 14px">
      <h3 class="blk-title">大创项目 xlsx 导入(v1 真语义:大创走 admin 导入通道)</h3>
      <p class="hint">
        列序:项目编号 | 项目名称 | 项目类型(国家级/省级/院级) | 起始日期 | 结束日期 | 负责人姓名 | 负责人学号 | 其他成员(顿号分隔) | 指导教师 | 经费(万元)。首行为表头;编号重复的行自动跳过(幂等)。
      </p>
      <el-upload
        drag
        accept=".xlsx"
        :auto-upload="false"
        :show-file-list="false"
        :on-change="(f: any) => onFileChange(f.raw)"
      >
        <el-icon :size="34" style="color: var(--brand)"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽 xlsx 到此处,或<em>点击选择文件</em></div>
      </el-upload>
      <p v-if="fileName" class="hint" style="margin-top: 8px">
        已解析:{{ fileName }}({{ rows.length }} 行)
      </p>
    </div>

    <div v-if="rows.length" class="c-panel pad" style="margin-bottom: 14px">
      <h3 class="blk-title">解析预览</h3>
      <el-table :data="rows" size="small" max-height="360">
        <el-table-column prop="rowNo" label="行" width="60" />
        <el-table-column prop="projectNo" label="项目编号" width="130" />
        <el-table-column prop="projectName" label="项目名称" min-width="200" />
        <el-table-column prop="projectType" label="类型" width="90" />
        <el-table-column prop="leaderName" label="负责人" width="100" />
        <el-table-column prop="supervisors" label="指导教师" width="140" />
        <el-table-column label="校验" width="200">
          <template #default="scope">
            <el-tag v-if="scope.row.error" type="danger" size="small">{{ scope.row.error }}</el-tag>
            <el-tag v-else type="success" size="small">通过</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-button
        type="primary"
        style="margin-top: 12px"
        data-testid="import-confirm"
        :disabled="busy"
        @click="confirmImport"
      >
        确认导入有效行
      </el-button>
    </div>

    <div v-if="result" class="c-panel pad">
      <h3 class="blk-title">导入结果</h3>
      <p class="hint">
        成功 {{ result.imported }} 行 · 跳过 {{ result.skipped }} 行 · 失败 {{ result.errors.length }} 行
      </p>
      <ul class="err-list">
        <li v-for="e in result.errors" :key="e">{{ e }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.blk-title { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.hint { font-size: 0.8rem; color: var(--ink-2); margin: 0 0 12px; line-height: 1.7; }
.err-list {
  font-size: 0.8rem;
  color: var(--sev-error);
  padding-left: 18px;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
}
</style>
