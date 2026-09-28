<template>
  <div class="teacher-submit">
    <ContentWrap>
      <div class="flex items-center justify-between mb-12px">
        <span class="text-16px font-600">提交成果</span>
        <span class="text-12px text-gray-500">累计提交 {{ total }} 条</span>
      </div>
      <div class="form-holder">
        <PendingSubmitForm @submitted="getList" />
      </div>
    </ContentWrap>

    <ContentWrap>
      <div class="mb-10px flex items-center justify-between">
        <span class="text-16px font-600">我的提交(最近 10 条)</span>
        <el-button :loading="loading" @click="getList">
          <Icon icon="ep:refresh" class="mr-5px" />刷新
        </el-button>
      </div>
      <el-table :data="list" v-loading="loading" border empty-text="暂无提交记录">
        <el-table-column label="成果" prop="title" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ titleOf(row) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="typeTone(row.achievementType)" size="small">
              {{ typeLabel(row.achievementType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTone(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="提交时间"
          prop="submitTime"
          width="170"
          :formatter="dateFormatter"
        />
      </el-table>
      <!-- v1 语义:提交页只展示最近 10 条作概览;完整分页/撤回/进度走管理员-教师共用的审核台 -->
    </ContentWrap>
  </div>
</template>

<script setup lang="ts">
/**
 * 教师提交成果(批15,对齐 v1 /teacher/achievement-submit):
 * 上传表单 + 最近 10 条提交概览。表单与学生门户共用同一组件;
 * 记录走 my-page(服务端强制按当前登录用户过滤,教师 token 拿到的就是教师自己的)。
 */
import PendingSubmitForm from '@/views/business/components/PendingSubmitForm.vue'
import { getMyPendingPage } from '@/api/business/achievement'
import { dateFormatter } from '@/utils/formatTime'

defineOptions({ name: 'TeacherSubmit' })

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

const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v || '-'
const typeTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ award: 'primary', patent: 'success', software: 'warning', innovation: 'info' } as const)[v] || 'danger'
const statusLabel = (v: string) => STATUS_OPTIONS.find((s) => s.value === v)?.label || v || '-'
const statusTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ pending: 'warning', archived: 'success', rejected: 'danger' } as const)[v] || 'info'

/** achievementData 是 JSON 字符串,取最能代表这条记录的字段当标题(与门户「我的提交」同口径) */
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

const getList = async () => {
  loading.value = true
  try {
    const data = await getMyPendingPage({ pageNo: 1, pageSize: 10 })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(getList)
</script>

<style scoped>
.form-holder {
  max-width: 720px;
}
</style>
