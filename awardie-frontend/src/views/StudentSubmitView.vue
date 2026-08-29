<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const API = '/api/v2'
const submitting = ref(false)
const form = reactive({
  competition_name: '',
  award_level: '省级一等奖',
  competition_level: 'A类',
  winner_name: '',
  supervisor_name: '',
  certificate_id: '',
  date: '',
  project_title: '',
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
    fd.append('achievement_type', 'award')
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
      <h2>提交奖状(award)</h2>
      <el-form label-position="top">
        <el-form-item label="竞赛名称">
          <el-input
            v-model="form.competition_name"
            placeholder="如:挑战杯"
          />
        </el-form-item>
        <el-form-item label="获奖等级">
          <el-input v-model="form.award_level" />
        </el-form-item>
        <el-form-item label="竞赛级别">
          <el-input
            v-model="form.competition_level"
            placeholder="如:A类"
          />
        </el-form-item>
        <el-form-item label="获奖人">
          <el-input v-model="form.winner_name" />
        </el-form-item>
        <el-form-item label="指导教师">
          <el-input v-model="form.supervisor_name" />
        </el-form-item>
        <el-form-item label="证书编号">
          <el-input v-model="form.certificate_id" />
        </el-form-item>
        <el-form-item label="获奖日期(YYYY-MM 或 YYYY-MM-DD)">
          <el-input v-model="form.date" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="form.project_title" />
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
