<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ensureCsrf, xsrfToken, apiJson } from '../composables/useCsrf'

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
const myAwards = ref<Array<Record<string, unknown>>>([])

// 时间线(#11 UI 补齐)
const timelineVisible = ref(false)
const timelineFor = ref<number | null>(null)
const timeline = ref<Array<Record<string, unknown>>>([])
const ACTION_LABELS: Record<number, string> = {
  1: '提交', 2: 'AI 审核', 3: 'AI 通过', 4: 'AI 驳回', 5: '教师复核',
  6: '审核通过', 7: '驳回打回', 8: '入库', 9: '修改字段', 10: '删除/放弃',
}

function onFileChange(evt: Event) {
  const target = evt.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
}

function countBy(status: string): number {
  return submissions.value.filter((r) => r.status === status).length
}

async function loadMine() {
  const resp = await fetch(`${API}/student/pending`, { credentials: 'include' })
  const body = (await resp.json()) as { code: number; data?: Array<Record<string, unknown>> }
  submissions.value = body.code === 0 ? (body.data ?? []) : []
}

async function loadAwards() {
  const body = await apiJson('GET', `${API}/student/awards`)
  myAwards.value = body.code === 0 ? (body.data ?? []) : []
}

async function openTimeline(id: number) {
  const body = await apiJson('GET', `${API}/student/timeline/${id}`)
  if (body.code === 0) {
    timeline.value = body.data
    timelineFor.value = id
    timelineVisible.value = true
  } else {
    ElMessage.error(body.message)
  }
}

onMounted(() => { loadMine(); loadAwards() })

async function onSubmit() {
  if (!file.value) {
    ElMessage.warning('请选择证书文件(jpg/png/pdf,≤10MB)')
    return
  }
  submitting.value = true
  try {
    await ensureCsrf()
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('achievement_type', achievementType.value)
    fd.append('data', JSON.stringify(form))
    const resp = await fetch(`${API}/student/submit`, {
      method: 'POST', credentials: 'include', body: fd,
      headers: { 'X-XSRF-TOKEN': xsrfToken() },
    })
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

    <!-- #37 对照 v1 student/submissions.html:统计卡四列(基于全部提交) -->
    <el-card class="pane">
      <h2>提交统计</h2>
      <div class="stat-grid">
        <div class="stat">
          <div class="num ink">
            {{ submissions.length }}
          </div>
          <div class="lbl">
            全部提交
          </div>
        </div>
        <div class="stat">
          <div class="num yellow">
            {{ countBy('pending') }}
          </div>
          <div class="lbl">
            待审核
          </div>
        </div>
        <div class="stat">
          <div class="num green">
            {{ countBy('archived') }}
          </div>
          <div class="lbl">
            已通过
          </div>
        </div>
        <div class="stat">
          <div class="num red">
            {{ countBy('rejected') }}
          </div>
          <div class="lbl">
            已驳回
          </div>
        </div>
      </div>
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
          width="80"
        >
          <template #default="scope">
            <a :href="`${API}/files/${scope.row.id}/download`">下载</a>
          </template>
        </el-table-column>
        <el-table-column
          label="时间线"
          width="90"
        >
          <template #default="scope">
            <el-button
              size="small"
              @click="openTimeline(scope.row.id)"
            >
              查看
            </el-button>
          </template>
        </el-table-column>
        <el-table-column
          prop="submitTime"
          label="提交时间"
        />
      </el-table>

      <h2 style="margin-top: 20px">
        我的成果(已入库)
      </h2>
      <el-table
        :data="myAwards"
        size="small"
      >
        <el-table-column
          prop="id"
          label="#"
          width="70"
        />
        <el-table-column
          prop="competition_name"
          label="竞赛"
        />
        <el-table-column
          prop="award_level"
          label="等级"
          width="120"
        />
        <el-table-column
          prop="winner_name"
          label="获奖人"
          width="100"
        />
        <el-table-column
          prop="date"
          label="日期"
          width="100"
        />
      </el-table>
    </el-card>

    <el-dialog
      v-model="timelineVisible"
      :title="`时间线 #${timelineFor ?? ''}`"
      width="480px"
    >
      <el-timeline v-if="timeline.length">
        <el-timeline-item
          v-for="(ev, i) in timeline"
          :key="i"
          :timestamp="String(ev.createdAt ?? '')"
        >
          <b>[{{ ACTION_LABELS[Number(ev.actionType)] ?? ev.actionType }}]</b>
          {{ ev.changeDetail && String(ev.changeDetail).includes('"message"')
            ? JSON.parse(String(ev.changeDetail)).message : ev.changeDetail }}
          <span class="op">{{ ev.operatorName ? `(${ev.operatorName})` : '' }}</span>
        </el-timeline-item>
      </el-timeline>
      <el-empty
        v-else
        description="暂无留痕记录(该行创建于留痕功能上线前)"
      />
      <template #footer>
        <el-button @click="timelineVisible = false">
          关闭
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.submit-page { display: flex; gap: 16px; }
.pane { flex: 1; background: var(--panel); }
h2 { margin-top: 0; color: var(--ink); }
.op { color: var(--ink-2); font-size: 12px; }
.stat-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
}
.stat { text-align: center; }
.num { font-size: 1.7rem; font-weight: 700; }
.num.ink { color: var(--ink); }
.num.yellow { color: var(--sev-warning); }
.num.green { color: #16a34a; }
.num.red { color: var(--sev-error); }
.lbl { font-size: 0.82rem; color: var(--ink-2); margin-top: 4px; }
</style>
