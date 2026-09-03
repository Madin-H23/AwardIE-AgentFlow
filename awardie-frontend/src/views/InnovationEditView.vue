<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-T 对照 v1 admin/innovation/edit.html(1121 行)+view.html;负责人选择器简化为文本+三态徽章(01-方案 偏差)。
interface Lab { id: number; name: string }
interface LeaderStatus { name: string; studentId: string; status: 'matched' | 'ambiguous' | 'not_found'; id?: number }
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const loading = ref(true)
const form = reactive({
  projectNo: '', projectName: '', projectType: '', status: '进行中',
  startDate: '', endDate: '', fundingAmount: null as number | null,
  studentLeaderName: '', studentLeaderId: '', supervisors: '', laboratoryId: null as number | null,
})
const membersText = ref('')
// otherMembers 原结构透传:未改动时回传原 JSON(元素可为 {姓名,学号} 对象),避免对象退化成字符串
let rawMembers: unknown[] | null = null
let membersSnapshot = ''
const laboratories = ref<Lab[]>([])
const leaderStatus = ref<LeaderStatus | null>(null)
const sys = reactive({ submitterType: '', submitterId: null as number | null, submitTime: '' })

const badge = computed(() => {
  const st = leaderStatus.value?.status
  return st === 'matched' ? 'success' : st === 'ambiguous' ? 'warning' : 'danger'
})
const badgeText = computed(() => {
  const st = leaderStatus.value?.status
  return st === 'matched' ? '已匹配' : st === 'ambiguous' ? '重名' : '未查到'
})

function fmtMember(x: unknown): string {
  if (x && typeof x === 'object') {
    const o = x as Record<string, unknown>
    const name = String(o['姓名'] ?? o['name'] ?? '')
    const no = String(o['学号'] ?? o['studentId'] ?? '')
    return no ? `${name}(${no})` : name
  }
  return String(x ?? '')
}

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/innovation/${id}/edit-detail`)
  if (body.code !== 0) {
    ElMessage.error(body.message ?? '大创项目不存在')
    loading.value = false
    return
  }
  const d = body.data
  Object.assign(form, {
    projectNo: d.projectNo ?? '', projectName: d.projectName ?? '',
    projectType: d.projectType ?? '', status: d.status ?? '进行中',
    startDate: d.startDate ?? '', endDate: d.endDate ?? '', fundingAmount: d.fundingAmount,
    studentLeaderName: d.studentLeaderName ?? '', studentLeaderId: d.studentLeaderId ?? '',
    supervisors: d.supervisors ?? '', laboratoryId: d.laboratoryId,
  })
  leaderStatus.value = d.leaderStatus ?? null
  laboratories.value = d.laboratories
  try {
    const m = d.otherMembers ? JSON.parse(d.otherMembers) : null
    if (Array.isArray(m)) {
      rawMembers = m
      membersText.value = m.map(fmtMember).join('、')
      membersSnapshot = membersText.value
    }
  } catch {
    membersText.value = ''
  }
  Object.assign(sys, {
    submitterType: d.submitterType ?? '', submitterId: d.submitterId, submitTime: d.submitTime ?? '',
  })
  loading.value = false
})

async function save() {
  if (!form.projectName.trim()) {
    ElMessage.warning('项目名称必填')
    return
  }
  const members: unknown[] = membersText.value.trim() === membersSnapshot && rawMembers
    ? rawMembers
    : membersText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  const body = await apiJson('PUT', `/api/v2/admin/innovation/${id}`, { ...form, otherMembers: members })
  if (body.code === 0) {
    ElMessage.success('已更新')
    router.push('/admin/achievements')
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>大创项目详情/编辑 #{{ id }}</h1>
      <div>
        <el-button type="primary" data-testid="innovation-edit-save" @click="save">保存</el-button>
        <el-button @click="router.push('/admin/achievements')">返回列表</el-button>
      </div>
    </div>

    <div class="wrap">
      <div class="c-panel pad">
        <h3 class="blk-title">基本信息</h3>
        <div class="frm">
          <label>项目编号</label>
          <el-input v-model="form.projectNo" />
          <label>项目类型</label>
          <el-select v-model="form.projectType" clearable>
            <el-option v-for="t in ['国家级', '省级', '院级']" :key="t" :value="t" :label="t" />
          </el-select>
          <label>项目名称 <span class="req">*</span></label>
          <el-input v-model="form.projectName" data-testid="innovation-edit-name" />
          <label>项目状态</label>
          <el-select v-model="form.status">
            <el-option v-for="s in ['进行中', '已结题', '终止']" :key="s" :value="s" :label="s" />
          </el-select>
          <div class="two">
            <div>
              <label>开始日期</label>
              <el-input v-model="form.startDate" placeholder="YYYY-MM-DD" />
            </div>
            <div>
              <label>结束日期</label>
              <el-input v-model="form.endDate" placeholder="YYYY-MM-DD" />
            </div>
          </div>
          <label>资助金额(元)</label>
          <el-input-number v-model="form.fundingAmount" :min="0" :precision="2" controls-position="right" />
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">人员与关联</h3>
        <div class="frm">
          <label>学生负责人</label>
          <div class="rel">
            <el-input v-model="form.studentLeaderName" data-testid="innovation-leader" />
            <el-tag v-if="leaderStatus" :type="badge" size="small" class="leader-tag" data-testid="innovation-leader-status">
              {{ badgeText }}
            </el-tag>
          </div>
          <label>负责人学号</label>
          <el-input v-model="form.studentLeaderId" placeholder="学号(用于精确匹配)" />
          <label>其他成员(顿号/逗号分隔)</label>
          <el-input v-model="membersText" placeholder="张三、李四" />
          <label>指导教师</label>
          <el-input v-model="form.supervisors" placeholder="多位教师逗号分隔" />
          <label>关联实验室</label>
          <el-select v-model="form.laboratoryId" clearable>
            <el-option v-for="l in laboratories" :key="l.id" :value="l.id" :label="l.name" />
          </el-select>
        </div>
      </div>
    </div>

    <div class="c-panel pad sys">
      <h3 class="blk-title">系统信息</h3>
      <p class="muted small">提交人类型:{{ sys.submitterType || '-' }} · 提交人ID:{{ sys.submitterId ?? '-' }} · 提交时间:{{ String(sys.submitTime).slice(0, 19).replace('T', ' ') || '-' }}</p>
    </div>
  </div>
</template>

<style scoped>
.wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.frm { display: flex; flex-direction: column; gap: 6px; }
.frm label { font-size: 0.82rem; color: var(--ink-2); }
.req { color: #ef4444; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.rel { position: relative; }
.leader-tag { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); }
.muted { color: var(--ink-2); }
.small { font-size: 0.78rem; }
.sys { margin-top: 14px; }
</style>
