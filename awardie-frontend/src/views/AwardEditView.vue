<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-R 对照 v1 admin/awards/edit.html(1676 行巨页)。
// 偏差(01-方案.md 声明):图片仅显示 hash 占位;保存不重验 is_abnormal;拖拽调序→上移/下移;requireAdmin。

interface NameStatus { name: string; status: 'matched' | 'ambiguous' | 'not_found'; id?: number }
interface Opt { id: number; name: string; grade?: string; title?: string; major?: string; loginCode?: string }
interface AwardDetail {
  id: number; competitionId: number | null; competitionName: string | null
  competitionLevel: string | null; awardLevel: string | null; year: number | null
  track: string | null; certificateId: string | null; projectTitle: string | null
  date: string | null; province: string | null; issuer: string | null
  laboratoryId: number | null; grantedRole: string | null
  winnerName: string | null; supervisorName: string | null
  imageHash: string | null; certificatePath: string | null; isAbnormal: boolean; validationResult: string | null; ocrResult?: string
  studentWinners: Opt[]; teacherWinners: Opt[]; supervisors: Opt[]; relatedStudents: Opt[]
  winnerStatus: NameStatus[]; supervisorStatus: NameStatus[]
  competitions: Opt[]; teachers: Opt[]; students: Opt[]; laboratories: Opt[]
  defaultLaboratoryId: number | null
}

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const loading = ref(true)
const certType = ref<'student' | 'teacher'>('student')

const form = reactive({
  competitionId: null as number | null,
  competitionLevel: '',
  awardLevel: '',
  year: null as number | null,
  track: '',
  certificateId: '',
  projectTitle: '',
  date: '',
  province: '',
  issuer: '',
  laboratoryId: null as number | null,
})
const imageHash = ref('')
const isAbnormal = ref(false)
const validationResult = ref<string | null>(null)
const ocrResult = ref('')

const competitions = ref<Opt[]>([])
const teachers = ref<Opt[]>([])
const students = ref<Opt[]>([])
const laboratories = ref<Opt[]>([])

// 获奖者:名单徽章(winner_name 全量,含未查到)+ 匹配 id
const studentBadges = ref<NameStatus[]>([])
const teacherBadges = ref<NameStatus[]>([])
const studentInput = ref('')
const teacherInput = ref('')
// 指导教师:可调序徽章
const supervisorBadges = ref<NameStatus[]>([])
const supervisorPick = ref<number | null>(null)
const relatedIds = ref<number[]>([])

const studentSuggestions = computed(() => {
  const kw = studentInput.value.trim()
  if (!kw) return []
  return students.value.filter((s) => s.name.includes(kw)).slice(0, 10)
})
const validationIssues = computed<string[]>(() => {
  if (!isAbnormal.value || !validationResult.value) return []
  try {
    const v = JSON.parse(validationResult.value)
    if (Array.isArray(v?.issues)) return v.issues.map(String)
    if (typeof v?.message === 'string') return [v.message]
  } catch {
    return [validationResult.value]
  }
  return []
})

function badgeType(st: string) {
  return st === 'matched' ? 'primary' : st === 'ambiguous' ? 'warning' : 'danger'
}
function badgeSuffix(st: string) {
  return st === 'matched' ? '' : st === 'ambiguous' ? '(重名)' : '(未查到)'
}

// 批 2 证书链:真图显示+上传/替换(清偿 Fix-R"hash 占位"偏差)
const certificatePath = ref<string | null>(null)
const certFile = ref<File | null>(null)
const certUploading = ref(false)

function onCertChange(file: UploadFile) {
  certFile.value = file.raw as File
}

async function uploadCert() {
  if (!certFile.value) return ElMessage.warning('请选择证书图片')
  certUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', certFile.value)
    const token = document.cookie.match(/(?:^|; )XSRF-TOKEN=([^;]*)/)
    const resp = await fetch(`/api/v2/admin/awards/${id}/certificate`, {
      method: 'POST', body: fd, credentials: 'include',
      headers: token ? { 'X-XSRF-TOKEN': decodeURIComponent(token[1]) } : {},
    })
    const body = await resp.json()
    if (body.code === 0) {
      certificatePath.value = body.data.path
      certFile.value = null
      ElMessage.success('证书图已上传')
    } else {
      ElMessage.error(body.message ?? '上传失败')
    }
  } finally {
    certUploading.value = false
  }
}

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/awards/${id}/edit-detail`)
  if (body.code !== 0) {
    ElMessage.error(body.message ?? '奖状不存在')
    loading.value = false
    return
  }
  const d = body.data as AwardDetail
  certificatePath.value = d.certificatePath ?? null
  Object.assign(form, {
    competitionId: d.competitionId, competitionLevel: d.competitionLevel ?? '',
    awardLevel: d.awardLevel ?? '', year: d.year, track: d.track ?? '',
    certificateId: d.certificateId ?? '', projectTitle: d.projectTitle ?? '',
    date: d.date ?? '', province: d.province ?? '', issuer: d.issuer ?? '',
    laboratoryId: d.laboratoryId ?? d.defaultLaboratoryId,
  })
  imageHash.value = d.imageHash ?? ''
  isAbnormal.value = !!d.isAbnormal
  validationResult.value = d.validationResult
  ocrResult.value = d.ocrResult ?? ''
  certType.value = d.grantedRole && d.grantedRole.includes('教师') ? 'teacher' : 'student'
  competitions.value = d.competitions
  teachers.value = d.teachers
  students.value = d.students
  laboratories.value = d.laboratories
  studentBadges.value = d.winnerStatus
  teacherBadges.value = d.winnerStatus
  supervisorBadges.value = d.supervisorStatus
  relatedIds.value = d.relatedStudents.map((s) => s.id)
  loading.value = false
})

function addStudentName(name: string) {
  const n = name.trim()
  if (!n) return
  if (!studentBadges.value.some((b) => b.name === n)) {
    const hit = students.value.find((s) => s.name === n)
    studentBadges.value.push({ name: n, status: hit ? 'matched' : 'not_found', id: hit?.id })
  }
  studentInput.value = ''
}
function addTeacherName(name: string) {
  const n = name.trim()
  if (!n) return
  if (!teacherBadges.value.some((b) => b.name === n)) {
    const hit = teachers.value.find((t) => t.name === n)
    teacherBadges.value.push({ name: n, status: hit ? 'matched' : 'not_found', id: hit?.id })
  }
  teacherInput.value = ''
}
function addSupervisor() {
  if (supervisorPick.value == null) return
  const t = teachers.value.find((x) => x.id === supervisorPick.value)
  if (t && !supervisorBadges.value.some((b) => b.id === t.id)) {
    supervisorBadges.value.push({ name: t.name, status: 'matched', id: t.id })
  }
  supervisorPick.value = null
}
function moveSupervisor(i: number, dir: -1 | 1) {
  const j = i + dir
  if (j < 0 || j >= supervisorBadges.value.length) return
  const arr = supervisorBadges.value
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}
function idsOf(badges: NameStatus[]): number[] {
  return badges.filter((b) => b.status === 'matched' && b.id != null).map((b) => b.id as number)
}

async function save() {
  if (!form.competitionId) {
    ElMessage.warning('竞赛必填')
    return
  }
  const names = studentBadges.value.map((b) => b.name).join(', ')
  const body = await apiJson('PUT', `/api/v2/admin/awards/${id}`, {
    competitionId: form.competitionId,
    competitionLevel: form.competitionLevel || null,
    awardLevel: form.awardLevel || null,
    year: form.year,
    track: form.track || null,
    certificateId: form.certificateId || null,
    projectTitle: form.projectTitle || null,
    date: form.date || null,
    province: form.province || null,
    issuer: form.issuer || null,
    laboratoryId: form.laboratoryId,
    grantedRole: certType.value,
    studentWinnerNames: names || null,
    supervisorIds: idsOf(supervisorBadges.value),
    teacherWinnerIds: certType.value === 'teacher' ? idsOf(teacherBadges.value) : [],
    studentWinnerIds: certType.value === 'student' ? idsOf(studentBadges.value) : [],
    relatedStudentIds: relatedIds.value,
  })
  if (body.code === 0) {
    ElMessage.success('奖状已更新')
    router.push('/admin/achievements')
  } else {
    ElMessage.error(body.message ?? '更新失败')
  }
}

async function del() {
  try {
    await ElMessageBox.confirm(`确定删除奖状 #${id} 吗?存在关联数据时将被拒绝。`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  const body = await apiJson('DELETE', `/api/v2/admin/vault/awards/${id}`)
  if (body.code === 0) {
    ElMessage.success('已删除')
    router.push('/admin/achievements')
  } else {
    ElMessage.error(body.message ?? '删除失败')
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>奖状详情/编辑 #{{ id }}</h1>
      <div>
        <el-button type="primary" data-testid="award-edit-save" @click="save">保存</el-button>
        <el-button type="danger" plain @click="del">删除</el-button>
        <el-button @click="router.push('/admin/achievements')">返回列表</el-button>
      </div>
    </div>

    <el-alert
      v-if="isAbnormal && validationIssues.length"
      type="error" :closable="false" class="mb-3" data-testid="award-abnormal-alert"
    >
      <template #title>检测到以下问题需要修复</template>
      <ul class="issue-list">
        <li v-for="(it, i) in validationIssues" :key="i">{{ it }}</li>
      </ul>
    </el-alert>

    <div class="grid-3">
      <div class="c-panel pad">
        <h3 class="blk-title">基本信息</h3>
        <div class="frm">
          <label>竞赛 <span class="req">*</span></label>
          <el-select v-model="form.competitionId" filterable data-testid="award-edit-competition">
            <el-option v-for="c in competitions" :key="c.id" :value="c.id" :label="c.name" />
          </el-select>
          <label>竞赛等级</label>
          <el-select v-model="form.competitionLevel" clearable>
            <el-option v-for="lv in ['校赛', '区域赛', '省赛', '国赛', '国际赛']" :key="lv" :value="lv" :label="lv" />
          </el-select>
          <label>获奖等级</label>
          <el-select v-model="form.awardLevel" clearable>
            <el-option
              v-for="lv in ['特等奖', '一等奖', '二等奖', '三等奖', '优秀奖', '金奖', '银奖', '铜奖']"
              :key="lv" :value="lv" :label="lv"
            />
          </el-select>
          <label>年份</label>
          <el-input-number v-model="form.year" :min="2000" :max="2099" controls-position="right" />
          <label>赛道</label>
          <el-input v-model="form.track" placeholder="软件类、本科B组" />
          <label>证书编号</label>
          <el-input v-model="form.certificateId" />
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">其他信息</h3>
        <div class="frm">
          <label>项目名称</label>
          <el-input v-model="form.projectTitle" />
          <label>日期</label>
          <el-input v-model="form.date" placeholder="YYYY-MM-DD" />
          <label>省份</label>
          <el-input v-model="form.province" />
          <label>颁发机构</label>
          <el-input v-model="form.issuer" />
          <label>关联学生实验室</label>
          <el-select v-model="form.laboratoryId" clearable>
            <el-option v-for="l in laboratories" :key="l.id" :value="l.id" :label="l.name" />
          </el-select>
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">奖状图片</h3>
        <div class="img-box">
          <template v-if="certificatePath">
            <!-- @error:悬空引用(文件被清理/失存)降级到"可上传补齐"态,终验批补充 -->
            <img :src="`/api/v2/admin/awards/${id}/certificate`" alt="证书图" class="cert-img" @error="certificatePath = null">
          </template>
          <template v-else-if="imageHash">
            <el-empty description="仅有哈希无文件(历史数据),可上传补齐" :image-size="70" />
            <p class="muted small">image_hash: {{ imageHash }}</p>
          </template>
          <template v-else>
            <el-empty description="暂无图片" :image-size="70" />
          </template>
          <el-upload
            :auto-upload="false" :limit="1" accept="image/*"
            :on-change="onCertChange" data-testid="award-cert-file"
          >
            <el-button>选择图片</el-button>
          </el-upload>
          <el-button
            type="primary" :loading="certUploading"
            data-testid="award-cert-upload" @click="uploadCert"
          >
            上传证书图
          </el-button>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="c-panel pad">
        <h3 class="blk-title">关联信息</h3>
        <div class="mb-3">
          <label class="frm-label">证书类型 <span class="req">*</span></label>
          <el-radio-group v-model="certType">
            <el-radio-button value="student">学生证书</el-radio-button>
            <el-radio-button value="teacher">教师证书</el-radio-button>
          </el-radio-group>
        </div>

        <div v-if="certType === 'student'" class="mb-3 rel" data-testid="award-student-winners">
          <label class="frm-label">学生获奖者</label>
          <div class="badge-box">
            <el-tag
              v-for="(b, i) in studentBadges" :key="b.name + i"
              :type="badgeType(b.status)" closable class="badge"
              @close="studentBadges.splice(i, 1)"
            >{{ b.name }}{{ badgeSuffix(b.status) }}</el-tag>
          </div>
          <el-input
            v-model="studentInput" placeholder="输入学生姓名,按回车或逗号添加"
            data-testid="award-student-input"
            @keydown.enter.prevent="addStudentName(studentInput)"
            @update:model-value="(v: string) => { if (v.endsWith(',')) addStudentName(v.slice(0, -1)) }"
          />
          <div v-if="studentSuggestions.length" class="sug">
            <div
              v-for="s in studentSuggestions" :key="s.id" class="sug-item"
              @click="addStudentName(s.name)"
            >{{ s.name }}<span class="muted small">({{ s.grade }})</span></div>
          </div>
        </div>

        <div v-if="certType === 'teacher'" class="mb-3" data-testid="award-teacher-winners">
          <label class="frm-label">教师获奖者</label>
          <div class="badge-box">
            <el-tag
              v-for="(b, i) in teacherBadges" :key="b.name + i"
              :type="badgeType(b.status)" closable class="badge"
              @close="teacherBadges.splice(i, 1)"
            >{{ b.name }}{{ badgeSuffix(b.status) }}</el-tag>
          </div>
          <el-input
            v-model="teacherInput" placeholder="输入教师姓名,按回车或逗号添加"
            @keydown.enter.prevent="addTeacherName(teacherInput)"
            @update:model-value="(v: string) => { if (v.endsWith(',')) addTeacherName(v.slice(0, -1)) }"
          />
        </div>

        <div class="mb-3">
          <label class="frm-label">指导教师(顺序即署名顺序)</label>
          <div class="badge-box" data-testid="award-supervisors">
            <span v-for="(b, i) in supervisorBadges" :key="b.name + i" class="sup-badge">
              <el-tag :type="badgeType(b.status)" closable @close="supervisorBadges.splice(i, 1)">
                {{ b.name }}{{ badgeSuffix(b.status) }}
              </el-tag>
              <el-button size="small" text :disabled="i === 0" @click="moveSupervisor(i, -1)">↑</el-button>
              <el-button size="small" text :disabled="i === supervisorBadges.length - 1" @click="moveSupervisor(i, 1)">↓</el-button>
            </span>
          </div>
          <div class="row-add">
            <el-select v-model="supervisorPick" filterable placeholder="选择指导教师" clearable>
              <el-option v-for="t in teachers" :key="t.id" :value="t.id" :label="t.name" />
            </el-select>
            <el-button @click="addSupervisor">添加</el-button>
          </div>
        </div>

        <div v-if="certType === 'teacher'" class="mb-3">
          <label class="frm-label">关联学生</label>
          <el-select v-model="relatedIds" multiple filterable placeholder="教师证书可关联所指导的学生">
            <el-option
              v-for="s in students" :key="s.id" :value="s.id"
              :label="`${s.name}(${s.grade})`"
            />
          </el-select>
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">OCR 结果</h3>
        <pre v-if="ocrResult" class="ocr-pre">{{ ocrResult }}</pre>
        <p v-else class="muted small">暂无数据(OCR 重识别挂账)</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 14px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.frm { display: flex; flex-direction: column; gap: 6px; }
.frm label { font-size: 0.82rem; color: var(--ink-2); }
.frm-label { display: block; font-size: 0.85rem; color: var(--ink); margin-bottom: 6px; }
.req { color: #ef4444; }
.mb-3 { margin-bottom: 16px; }
.badge-box { display: flex; flex-wrap: wrap; gap: 6px; min-height: 32px; padding: 6px; border: 1px dashed var(--line); border-radius: 6px; margin-bottom: 8px; }
.badge { margin: 0; }
.sup-badge { display: inline-flex; align-items: center; gap: 0; }
.row-add { display: flex; gap: 8px; }
.sug { position: absolute; left: 0; right: 0; top: 100%; z-index: 20; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; max-height: 200px; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,.12); }
.sug-item { padding: 6px 10px; cursor: pointer; font-size: 0.85rem; }
.sug-item:hover { background: color-mix(in srgb, var(--ink) 5%, transparent); }
.rel { position: relative; }
.img-box { text-align: center; padding: 12px 0; display: flex; flex-direction: column; gap: 8px; align-items: center; }
.cert-img { max-width: 100%; max-height: 320px; border: 1px solid var(--line); border-radius: 6px; }
.ocr-pre { background: color-mix(in srgb, var(--ink) 4%, transparent); padding: 10px; border-radius: 6px; font-size: 0.78rem; max-height: 220px; overflow-y: auto; white-space: pre-wrap; }
.issue-list { margin: 4px 0 0; padding-left: 18px; }
.muted { color: var(--ink-2); }
.small { font-size: 0.78rem; }
</style>
