<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const API = '/api/v2'
const submitting = ref(false)
const achievementType = ref('award')
const typeOptions = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软件著作权' },
  { value: 'innovation', label: '创新创业项目' },
  { value: 'other', label: '其他' },
]
const typeFields: Record<string, Array<{ key: string; label: string }>> = {
  award: [
    { key: 'competition_name', label: '竞赛名称' },
    { key: 'award_level', label: '获奖等级' },
    { key: 'competition_level', label: '竞赛级别' },
    { key: 'winner_name', label: '获奖人' },
    { key: 'supervisor_name', label: '指导教师' },
    { key: 'certificate_id', label: '证书编号' },
    { key: 'date', label: '获奖日期(YYYY-MM)' },
    { key: 'project_title', label: '项目名称' },
  ],
  patent: [
    { key: 'patent_name', label: '专利名称' },
    { key: 'application_number', label: '申请号(CN 开头)' },
    { key: 'patent_type', label: '专利类型(发明专利/实用新型/外观设计)' },
  ],
  software: [
    { key: 'software_name', label: '软件名称' },
    { key: 'registration_number', label: '登记号(11 位,如 2023SR123456)' },
  ],
  innovation: [{ key: 'project_name', label: '项目名称' }],
  other: [{ key: 'title', label: '成果名称' }],
}
const form = reactive<Record<string, string>>({
  competition_name: '', award_level: '省级一等奖', competition_level: 'A类',
  winner_name: '', supervisor_name: '', certificate_id: '', date: '', project_title: '',
  patent_name: '', application_number: '', patent_type: '',
  software_name: '', registration_number: '', title: '',
})
const file = ref<File | null>(null)
const submissions = ref<Array<Record<string, unknown>>>([])

function onFileChange(evt: Event) {
  const target = evt.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
}

async function loadMine() {
  const resp = await fetch(`${API}/student/pending`, { credentials: 'include' })
  const body = (await resp.json()) as { code: number; data?: Array<Record<string, unknown>> }
  submissions.value = body.code === 0 ? (body.data ?? []) : []
}

onMounted(loadMine)

async function onSubmit() {
  if (!file.value) {
    ElMessage.warning('请选择证书文件(jpg/png/pdf,≤10MB)')
    return
  }
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('achievement_type', achievementType.value)
    fd.append('data', JSON.stringify(form))
    const resp = await fetch(`${API}/student/submit`, { method: 'POST', credentials: 'include', body: fd })
    const body = await resp.json()
    if (body.code === 0) {
      ElMessage.success(`提交成功(#${body.data.id})${body.data.isValid ? '' : ',存在待人工确认项'}`)
      await loadMine()
    } else {
      ElMessage.error(body.message)
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="submit-page">
    <el-card class="pane">
      <h2>提交成果</h2>
      <el-form label-position="top">
        <el-form-item label="成果类型">
          <el-select v-model="achievementType">
            <el-option
              v-for="t in typeOptions"
              :key="t.value"
              :value="t.value"
              :label="t.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-for="f in typeFields[achievementType]"
          :key="f.key"
          :label="f.label"
        >
          <el-input v-model="form[f.key]" />
        </el-form-item>
        <el-form-item label="证书文件(jpg/png/pdf,≤10MB)">
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            @change="onFileChange"
          >
        </el-form-item>
        <el-button
          type="primary"
          :loading="submitting"
          @click="onSubmit"
        >
          提交审核
        </el-button>
      </el-form>
    </el-card>

    <el-card class="pane">
      <h2>我的提交</h2>
      <el-table
        :data="submissions"
        size="small"
      >
        <el-table-column
          prop="id"
          label="#"
          width="70"
        />
        <el-table-column
          prop="achievementType"
          label="类型"
          width="90"
        />
        <el-table-column
          prop="status"
          label="状态"
          width="100"
        />
        <el-table-column
          label="文件"
          width="110"
        >
          <template #default="scope">
            <a :href="`${API}/files/${scope.row.id}/download`">下载</a>
          </template>
        </el-table-column>
        <el-table-column
          prop="submitTime"
          label="提交时间"
        />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.submit-page { display: flex; gap: 16px; max-width: 1100px; margin: 24px auto; }
.pane { flex: 1; background: var(--panel); }
h2 { margin-top: 0; color: var(--ink); }
</style>
