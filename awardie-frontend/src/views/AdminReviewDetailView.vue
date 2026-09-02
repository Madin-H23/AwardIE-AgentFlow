<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-F 对照 v1 admin/review/view.html:审核详情——状态提示/提交信息/成果数据/验证结果/审核操作/审核历史。
interface Pending {
  id: number
  achievementType: string
  achievementData: string
  validationResult: string | null
  submitterType: string
  submitterId: number | null
  status: string
  reviewerId: number | null
  reviewTime: string | null
  reviewComment: string | null
  submitTime: string | null
  createdAt: string | null
}
interface Validation {
  is_valid: boolean
  content_issues: string[]
  completeness_issues: string[]
}

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const p = ref<Pending | null>(null)
const loading = ref(true)
const approveComment = ref('')
const rejectComment = ref('')

const TYPE_LABEL: Record<string, string> = {
  award: '奖状', patent: '专利', software: '软著', innovation: '大创', other: '其他',
}
const STATUS_TEXT: Record<string, string> = {
  pending: '待审核', archived: '已通过', rejected: '已拒绝',
}
const STATUS_TYPE: Record<string, string> = {
  pending: 'warning', archived: 'success', rejected: 'error',
}

const validation = computed<Validation | null>(() => {
  if (!p.value?.validationResult) return null
  try {
    return JSON.parse(p.value.validationResult)
  } catch {
    return null
  }
})

const prettyData = computed(() => {
  if (!p.value) return ''
  try {
    return JSON.stringify(JSON.parse(p.value.achievementData), null, 2)
  } catch {
    return p.value.achievementData
  }
})

function fmt(v: string | null): string {
  return v ? v.replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  loading.value = true
  try {
    const body = await apiJson('GET', `/api/v2/admin/achievements/${id}`)
    if (body.code === 0) p.value = body.data
    else ElMessage.error(body.message ?? '记录不存在')
  } finally {
    loading.value = false
  }
}

async function review(action: 'approve' | 'reject') {
  const comment = action === 'approve' ? approveComment.value : rejectComment.value
  const body = await apiJson('POST', `/api/v2/admin/achievements/${id}/review`, { action, comment })
  if (body.code === 0) {
    ElMessage.success(action === 'approve' ? '已通过' : '已拒绝')
    await load()
  } else {
    ElMessage.error(body.message)
  }
}

function goBack() {
  router.push('/admin/review')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>审核详情 #{{ id }}</h1>
      <el-button @click="goBack">返回列表</el-button>
    </div>

    <el-alert
      v-if="p"
      :title="STATUS_TEXT[p.status] ?? p.status"
      :type="p.status === 'pending' ? 'warning' : p.status === 'archived' ? 'success' : 'error'"
      :closable="false"
      show-icon
      style="margin-bottom: 14px"
    />

    <div
      v-if="p"
      class="grid"
    >
      <div class="col-main">
        <div class="c-panel pad" style="margin-bottom: 14px">
          <h3 class="blk-title">提交信息</h3>
          <div class="d-row"><span class="d-k">成果类型</span><span>{{ TYPE_LABEL[p.achievementType] ?? p.achievementType }}</span></div>
          <div class="d-row"><span class="d-k">提交人</span><span>{{ p.submitterType }} #{{ p.submitterId }}</span></div>
          <div class="d-row"><span class="d-k">提交时间</span><span>{{ fmt(p.submitTime) }}</span></div>
          <div class="d-row"><span class="d-k">当前状态</span><span>{{ STATUS_TEXT[p.status] ?? p.status }}</span></div>
        </div>

        <div class="c-panel pad" style="margin-bottom: 14px">
          <h3 class="blk-title">成果数据</h3>
          <pre class="json">{{ prettyData }}</pre>
        </div>

        <div
          v-if="validation"
          class="c-panel pad"
        >
          <h3 class="blk-title">验证结果</h3>
          <p :class="validation.is_valid ? 'ok-text' : 'err-text'">
            {{ validation.is_valid ? '数据验证通过' : '数据验证失败' }}
          </p>
          <ul v-if="validation.content_issues?.length" class="issue err-text">
            <li v-for="i in validation.content_issues" :key="i">{{ i }}</li>
          </ul>
          <ul v-if="validation.completeness_issues?.length" class="issue warn-text">
            <li v-for="i in validation.completeness_issues" :key="i">{{ i }}</li>
          </ul>
        </div>
      </div>

      <div class="col-side">
        <div
          v-if="p.status === 'pending'"
          class="c-panel pad"
          style="margin-bottom: 14px"
        >
          <h3 class="blk-title">审核操作</h3>
          <el-input
            v-model="approveComment"
            type="textarea"
            :rows="3"
            placeholder="审核意见(可选)"
            style="margin-bottom: 10px"
          />
          <el-button
            type="success"
            style="width: 100%"
            data-testid="view-approve"
            @click="review('approve')"
          >
            审核通过
          </el-button>
          <el-divider />
          <el-input
            v-model="rejectComment"
            type="textarea"
            :rows="3"
            placeholder="拒绝原因(BR-5 必填)"
            style="margin-bottom: 10px"
          />
          <el-button
            type="danger"
            style="width: 100%"
            :disabled="!rejectComment.trim()"
            data-testid="view-reject"
            @click="review('reject')"
          >
            拒绝
          </el-button>
        </div>

        <div
          v-else
          class="c-panel pad"
        >
          <h3 class="blk-title">审核历史</h3>
          <div class="d-row"><span class="d-k">审核人ID</span><span>{{ p.reviewerId ?? '-' }}</span></div>
          <div class="d-row"><span class="d-k">审核时间</span><span>{{ fmt(p.reviewTime) }}</span></div>
          <div class="d-row"><span class="d-k">审核意见</span><span>{{ p.reviewComment || '-' }}</span></div>
        </div>

        <div class="c-panel pad">
          <h3 class="blk-title">系统信息</h3>
          <div class="d-row"><span class="d-k">ID</span><span>{{ p.id }}</span></div>
          <div class="d-row"><span class="d-k">创建时间</span><span>{{ fmt(p.createdAt) }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; align-items: start; }
.col-side { display: flex; flex-direction: column; }
.blk-title { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.d-row {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 7px 0; border-bottom: 1px dashed var(--line); font-size: 0.88rem;
}
.d-k { color: var(--ink-2); flex-shrink: 0; }
.json {
  font-size: 0.82rem; max-height: 400px; overflow-y: auto;
  background: var(--sb-foot); padding: 10px; border-radius: 6px; margin: 0;
}
.ok-text { color: #16a34a; }
.err-text { color: var(--sev-error); }
.warn-text { color: var(--sev-warning); }
.issue { padding-left: 18px; margin: 6px 0; font-size: 0.85rem; }
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
