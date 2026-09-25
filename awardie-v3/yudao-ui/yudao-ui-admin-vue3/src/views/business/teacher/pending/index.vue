<template>
  <ContentWrap>
    <el-alert
      title="您在这里做的是初审:「通过」会把成果物化写入成果库,「驳回」需填写原因,原因会写入留痕并展示给学生"
      type="warning"
      :closable="false"
      class="mb-12px"
    />
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="80px"
      class="-mb-20px"
    >
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="成果类型" prop="achievementType">
        <el-select v-model="queryParams.achievementType" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="t in TYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <el-table
      v-loading="loading"
      :data="pagedList"
      row-key="id"
      border
      empty-text="没有符合条件的待审成果"
      @row-click="openDetail"
    >
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="提交人" prop="submitterName" min-width="140" show-overflow-tooltip />
      <el-table-column label="提交人类型" width="110" align="center">
        <template #default="scope">
          <el-tag :type="submitterTone(scope.row.submitterType)" size="small">
            {{ submitterLabel(scope.row.submitterType) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="成果类型" width="110" align="center">
        <template #default="scope">
          <el-tag :type="typeTone(scope.row.achievementType)" size="small">
            {{ typeLabel(scope.row.achievementType) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="scope">
          <el-tag :type="statusTone(scope.row.status)" size="small">
            {{ statusLabel(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" prop="submitTime" width="180" align="center" :formatter="dateFormatter" />
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click.stop="openDetail(scope.row)">查看详情</el-button>
          <template v-if="scope.row.status === 'pending'">
            <el-button link type="success" @click.stop="openReview(scope.row, 'approve')">通过</el-button>
            <el-button link type="danger" @click.stop="openReview(scope.row, 'reject')">驳回</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <Pagination
      v-model:page="queryParams.pageNo"
      v-model:limit="queryParams.pageSize"
      :total="filteredList.length"
      @pagination="() => {}"
    />
  </ContentWrap>

  <!-- 详情:复用管理端同一套交互(文件预览 + 结构化字段 + AI 建议 + 留痕) -->
  <el-drawer v-model="detailVisible" title="待审成果详情" size="720px">
    <div v-if="detail" v-loading="detailLoading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="编号">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="提交人">
          {{ detail.submitterName || '-' }}({{ submitterLabel(detail.submitterType) }})
        </el-descriptions-item>
        <el-descriptions-item label="成果类型">
          <el-tag :type="typeTone(detail.achievementType)" size="small">
            {{ typeLabel(detail.achievementType) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTone(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ detail.submitTime || '-' }}</el-descriptions-item>
        <el-descriptions-item label="校验结果">
          {{ validationLabel(detail.validationResult) }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.reviewComment" label="审核意见" :span="2">
          {{ detail.reviewComment }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="section-title">原始文件</div>
      <div v-loading="fileLoading" class="mb-12px">
        <img v-if="fileUrl" :src="fileUrl" class="file-preview" alt="待审成果文件" />
        <el-empty v-else-if="fileFailed" description="文件加载失败(可能已清理或无权限)" :image-size="60" />
        <el-skeleton v-else :rows="3" animated />
      </div>

      <div class="section-title">结构化字段</div>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="(v, k) in parsedData" :key="k" :label="k">
          {{ v === null || v === '' ? '-' : v }}
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-if="!Object.keys(parsedData).length" description="无结构化字段" :image-size="60" />

      <div class="section-title">AI 审核建议</div>
      <div v-loading="aiLoading">
        <template v-if="aiSuggest">
          <el-alert
            :title="`AI 建议:${decisionLabel(aiSuggest.decision)}`"
            :type="
              aiSuggest.decision === 'pass'
                ? 'success'
                : aiSuggest.decision === 'reject'
                  ? 'error'
                  : 'warning'
            "
            :closable="false"
          />
          <p v-if="aiSuggest.suggestion" class="mt-8px">{{ aiSuggest.suggestion }}</p>
          <p v-if="aiSuggest.degraded" class="mt-8px text-12px text-gray-500">
            AI Worker 降级模式({{ aiSuggest.message || '不可用' }}),建议仅供参考
          </p>
          <ul v-if="parsedIssues.length" class="issue-list">
            <li v-for="(issue, i) in parsedIssues" :key="i">{{ issue }}</li>
          </ul>
        </template>
        <el-empty v-else description="暂无 AI 建议" :image-size="60" />
      </div>

      <div class="section-title">审核留痕</div>
      <el-timeline v-if="timeline.length">
        <el-timeline-item
          v-for="item in timeline"
          :key="item.id"
          :timestamp="item.createTime"
          placement="top"
        >
          <b>{{ actionLabel(item.actionType) }}</b>
          <span class="ml-8px text-12px text-gray-500">
            {{ item.operatorName || item.operatorCode || '-' }}
          </span>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无留痕" :image-size="60" />
    </div>
  </el-drawer>

  <Dialog v-model="reviewVisible" :title="reviewAction === 'approve' ? '通过确认' : '驳回确认'" width="520px">
    <el-alert
      v-if="reviewAction === 'approve'"
      type="warning"
      :closable="false"
      title="通过后会把这条成果物化写入成果库,此操作不可撤销"
      class="mb-12px"
    />
    <el-form label-width="80px">
      <el-form-item label="审核意见">
        <el-input
          v-model="reviewComment"
          type="textarea"
          :rows="4"
          :placeholder="reviewAction === 'reject' ? '驳回原因(必填,会写入留痕)' : '可选'"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button
        type="primary"
        :danger="reviewAction === 'reject'"
        :loading="reviewLoading"
        @click="submitReview"
        >确 定</el-button
      >
      <el-button @click="reviewVisible = false">取 消</el-button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { dateFormatter } from '@/utils/formatTime'
import {
  downloadPending,
  getAiSuggest,
  getPendingTimeline,
  getTeacherPendingList,
  reviewPending
} from '@/api/business/achievement'
import { useBlobUrl } from '../../components/useBlobUrl'

defineOptions({ name: 'TeacherPending' })

const message = useMessage()

const TYPE_OPTIONS = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]
const STATUS_OPTIONS = [
  { value: 'pending', label: '待审核' },
  { value: 'archived', label: '已入库' },
  { value: 'rejected', label: '已驳回' }
]
const ACTION_LABELS: Record<number, string> = {
  1: '提交',
  6: '审核通过',
  7: '驳回',
  8: '物化入库'
}

const typeLabel = (v: string) => TYPE_OPTIONS.find((t) => t.value === v)?.label || v || '-'
const typeTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ award: 'primary', patent: 'success', software: 'warning', innovation: 'info' } as const)[v] || 'danger'
const statusLabel = (v: string) => STATUS_OPTIONS.find((s) => s.value === v)?.label || v || '-'
const statusTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ pending: 'warning', archived: 'success', rejected: 'danger' } as const)[v] || 'info'
const submitterLabel = (v: string) =>
  ({ student: '学生', teacher: '教师', admin: '管理员' } as const)[v] || v || '-'
const submitterTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ student: 'primary', teacher: 'success', admin: 'warning' } as const)[v] || 'info'
const actionLabel = (v: number) => ACTION_LABELS[v] || String(v ?? '-')
const validationLabel = (v: string) =>
  ({ is_valid: '完整有效', content_issues: '内容有问题', completeness_issues: '字段缺失' } as const)[v] || v || '-'
const decisionLabel = (v: string) =>
  ({ pass: '通过', reject: '驳回', 'need-manual': '需人工判断' } as const)[v] || v || '-'

const loading = ref(false)
const allList = ref<any[]>([])

const queryParams = reactive({
  pageNo: 1,
  pageSize: 20,
  status: undefined as string | undefined,
  achievementType: undefined as string | undefined
})

const queryFormRef = ref()

const filteredList = computed(() => {
  if (!queryParams.achievementType) {
    return allList.value
  }
  return allList.value.filter((r) => r.achievementType === queryParams.achievementType)
})

const pagedList = computed(() => {
  const start = (queryParams.pageNo - 1) * queryParams.pageSize
  return filteredList.value.slice(start, start + queryParams.pageSize)
})

const getList = async () => {
  loading.value = true
  try {
    const params = queryParams.status ? { status: queryParams.status } : undefined
    allList.value = (await getTeacherPendingList(params)) || []
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  queryParams.pageNo = 1
  getList()
}

const resetQuery = () => {
  queryFormRef.value?.resetFields()
  queryParams.pageNo = 1
  getList()
}

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>()
const timeline = ref<any[]>([])
const aiLoading = ref(false)
const aiSuggest = ref<any>()

const { url: fileUrl, loading: fileLoading, failed: fileFailed, load: loadFile, revoke } =
  useBlobUrl(downloadPending)

const parsedData = computed<Record<string, any>>(() => {
  if (!detail.value?.achievementData) {
    return {}
  }
  try {
    return JSON.parse(detail.value.achievementData)
  } catch {
    return { 原始内容: detail.value.achievementData }
  }
})

const parsedIssues = computed<string[]>(() => {
  const raw = aiSuggest.value?.issuesJson
  if (!raw) {
    return []
  }
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map((i) => String(i)) : [JSON.stringify(parsed)]
  } catch {
    return [String(raw)]
  }
})

const openDetail = async (row: any) => {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = row
  timeline.value = []
  aiSuggest.value = undefined
  try {
    const [tl, ai] = await Promise.allSettled([
      getPendingTimeline(row.id),
      row.status === 'pending' ? getAiSuggest(row.id) : Promise.reject(new Error('skip'))
    ])
    if (tl.status === 'fulfilled') {
      timeline.value = tl.value || []
    }
    if (ai.status === 'fulfilled') {
      aiSuggest.value = ai.value
    }
  } finally {
    detailLoading.value = false
  }
  revoke()
  loadFile(row.id)
}

const reviewVisible = ref(false)
const reviewLoading = ref(false)
const reviewId = ref<number>()
const reviewAction = ref<'approve' | 'reject'>('approve')
const reviewComment = ref('')

const openReview = (row: any, action: 'approve' | 'reject') => {
  reviewId.value = row.id
  reviewAction.value = action
  reviewComment.value = ''
  reviewVisible.value = true
}

const submitReview = async () => {
  if (reviewAction.value === 'reject' && !reviewComment.value.trim()) {
    message.warning('驳回必须填写原因,原因会写入审核留痕并展示给学生')
    return
  }
  reviewLoading.value = true
  try {
    await reviewPending(reviewId.value as number, {
      action: reviewAction.value,
      comment: reviewComment.value.trim() || undefined
    })
    message.success(reviewAction.value === 'approve' ? '已通过并入库' : '已驳回')
    reviewVisible.value = false
    await getList()
  } finally {
    reviewLoading.value = false
  }
}

onMounted(getList)
</script>

<style scoped>
.section-title {
  margin: 20px 0 10px;
  font-size: 14px;
  font-weight: 600;
}
.file-preview {
  display: block;
  max-width: 100%;
  max-height: 420px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.issue-list {
  margin: 8px 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
