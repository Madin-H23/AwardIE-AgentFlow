<template>
  <div class="portal-page">
    <div class="filter-bar">
      <el-select v-model="queryParams.status" placeholder="全部状态" clearable @change="handleFilter">
        <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-button :loading="loading" @click="getList">
        <Icon icon="ep:refresh" class="mr-5px" />刷新
      </el-button>
    </div>

    <el-empty v-if="!loading && list.length === 0" description="还没有提交记录" />

    <div v-for="item in list" :key="item.id" class="record-card">
      <div class="record-head">
        <el-tag :type="typeTone(item.achievementType)" size="small">
          {{ typeLabel(item.achievementType) }}
        </el-tag>
        <el-tag :type="statusTone(item.status)" size="small" class="ml-6px">
          {{ statusLabel(item.status) }}
        </el-tag>
        <span class="record-time">{{ item.submitTime || '' }}</span>
      </div>

      <div class="record-title">{{ titleOf(item) }}</div>

      <!-- 驳回原因必须显眼:学生最需要知道的就是「为什么被拒」 -->
      <el-alert
        v-if="item.status === 'rejected' && item.reviewComment"
        type="error"
        :closable="false"
        class="mt-8px"
      >
        <template #title>驳回原因:{{ item.reviewComment }}</template>
      </el-alert>
      <el-alert
        v-else-if="item.status === 'archived'"
        type="success"
        :closable="false"
        class="mt-8px"
      >
        <template #title>已通过并入库,证书可在「我的证书」查看</template>
      </el-alert>

      <div class="record-actions">
        <el-button link type="primary" @click="openTimeline(item)">查看进度</el-button>
        <el-button
          v-if="item.status === 'pending'"
          link
          type="danger"
          @click="handleWithdraw(item)"
        >
          撤回
        </el-button>
      </div>
    </div>

    <Pagination
      v-if="total > queryParams.pageSize"
      v-model:page="queryParams.pageNo"
      v-model:limit="queryParams.pageSize"
      :total="total"
      @pagination="getList"
    />

    <el-drawer v-model="timelineVisible" title="提交进度" size="90%" direction="btt">
      <div v-loading="timelineLoading">
        <el-timeline v-if="timeline.length">
          <el-timeline-item
            v-for="t in timeline"
            :key="t.id"
            :timestamp="t.createTime"
            placement="top"
          >
            <b>{{ actionLabel(t.actionType) }}</b>
            <span class="ml-8px text-12px text-gray-500">
              {{ t.operatorName || t.operatorCode || '' }}
            </span>
            <div v-if="t.changeDetail" class="text-12px text-gray-500">{{ t.changeDetail }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无进度记录" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { getMyPendingPage, getPendingTimeline, withdrawPending } from '@/api/business/achievement'

defineOptions({ name: 'PortalSubmissions' })

const message = useMessage()

const TYPES = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]
const STATUS_OPTIONS = [
  { value: 'pending', label: '待审核' },
  { value: 'archived', label: '已通过' },
  { value: 'rejected', label: '已驳回' }
]
const ACTION_LABELS: Record<number, string> = {
  1: '提交',
  6: '审核通过',
  7: '驳回',
  8: '物化入库'
}

const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v || '-'
const typeTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ award: 'primary', patent: 'success', software: 'warning', innovation: 'info' } as const)[v] || 'danger'
const statusLabel = (v: string) => STATUS_OPTIONS.find((s) => s.value === v)?.label || v || '-'
const statusTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ pending: 'warning', archived: 'success', rejected: 'danger' } as const)[v] || 'info'
const actionLabel = (v: number) => ACTION_LABELS[v] || String(v ?? '-')

/** achievementData 是 JSON 字符串,取最能代表这条记录的字段当标题 */
const titleOf = (item: any) => {
  if (!item.achievementData) {
    return `提交 #${item.id}`
  }
  try {
    const d = JSON.parse(item.achievementData)
    const key =
      ['competition_name', 'patent_name', 'software_name', 'project_name', 'file_name'].find(
        (k) => d[k]
      ) || Object.keys(d)[0]
    return d[key] || `提交 #${item.id}`
  } catch {
    return `提交 #${item.id}`
  }
}

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  status: undefined as string | undefined
})

const getList = async () => {
  loading.value = true
  try {
    // 服务端强制按当前登录用户过滤,这里传什么 submitterId 都会被覆盖
    const data = await getMyPendingPage(queryParams)
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const handleFilter = () => {
  queryParams.pageNo = 1
  getList()
}

const handleWithdraw = async (item: any) => {
  await message.confirm('撤回后这条提交将不再进入审核队列,确认撤回?', '撤回提交')
  await withdrawPending(item.id)
  message.success('已撤回')
  if (list.value.length === 1 && queryParams.pageNo > 1) {
    queryParams.pageNo -= 1
  }
  await getList()
}

const timelineVisible = ref(false)
const timelineLoading = ref(false)
const timeline = ref<any[]>([])

const openTimeline = async (item: any) => {
  timelineVisible.value = true
  timelineLoading.value = true
  timeline.value = []
  try {
    timeline.value = (await getPendingTimeline(item.id)) || []
  } finally {
    timelineLoading.value = false
  }
}

onMounted(getList)
</script>

<style scoped>
.portal-page {
  max-width: 720px;
  margin: 0 auto;
}
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.filter-bar :deep(.el-select) {
  flex: 1;
}
.record-card {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgb(0 0 0 / 6%);
}
.record-head {
  display: flex;
  align-items: center;
}
.record-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.record-title {
  margin-top: 8px;
  font-size: 15px;
  font-weight: 500;
  word-break: break-all;
}
.record-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}
.record-actions :deep(.el-button) {
  min-height: 44px;
  padding: 0 8px;
}
</style>
