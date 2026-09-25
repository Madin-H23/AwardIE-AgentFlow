<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="80px"
      class="-mb-20px"
    >
      <el-form-item label="成果类型" prop="achievementKind">
        <el-select v-model="queryParams.achievementKind" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="t in KIND_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="动作" prop="actionType">
        <el-select v-model="queryParams.actionType" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="a in ACTION_OPTIONS" :key="a.value" :label="a.label" :value="a.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="操作人" prop="operatorKeyword">
        <el-input
          v-model="queryParams.operatorKeyword"
          placeholder="姓名或账号"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="时间区间" prop="createTime">
        <el-date-picker
          v-model="queryParams.createTime"
          type="datetimerange"
          value-format="YYYY-MM-DD HH:mm:ss"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <el-alert
      title="这里只记录成果审核留痕(提交/通过/驳回/物化);登录与系统操作日志在「系统管理 → 审计日志」"
      type="info"
      :closable="false"
      class="mb-12px"
    />
    <el-table v-loading="loading" :data="list" row-key="id" border empty-text="暂无审核留痕">
      <el-table-column type="expand">
        <template #default="scope">
          <div class="px-12px py-8px">
            <p class="mb-0">
              <span class="detail-label">变更详情:</span>
              <pre class="detail-json">{{ prettyDetail(scope.row.changeDetail) }}</pre>
            </p>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="成果编号" prop="achievementId" width="100" align="center" />
      <el-table-column label="成果类型" width="120" align="center">
        <template #default="scope">
          <el-tag :type="kindTone(scope.row.achievementKind)" size="small">
            {{ kindLabel(scope.row.achievementKind) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="动作" width="120" align="center">
        <template #default="scope">
          <el-tag :type="actionTone(scope.row.actionType)" size="small">
            {{ scope.row.actionLabel || actionLabel(scope.row.actionType) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="结果" width="90" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.actionResult === 1 ? 'success' : 'danger'" size="small">
            {{ scope.row.actionResult === 1 ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作人" min-width="160">
        <template #default="scope">
          <span>{{ scope.row.operatorName || '-' }}</span>
          <span v-if="scope.row.operatorCode" class="ml-4px text-12px text-gray-500">
            ({{ scope.row.operatorCode }})
          </span>
        </template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" min-width="200" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.remark || '-' }}</template>
      </el-table-column>
      <el-table-column label="发生时间" prop="createTime" width="180" align="center" :formatter="dateFormatter" />
    </el-table>

    <Pagination
      v-model:page="queryParams.pageNo"
      v-model:limit="queryParams.pageSize"
      :total="total"
      @pagination="getList"
    />
  </ContentWrap>
</template>

<script setup lang="ts">
import { dateFormatter } from '@/utils/formatTime'
import { getAuditLogPage } from '@/api/business'

defineOptions({ name: 'Logs' })

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const KIND_OPTIONS = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]

// 动作码与后端 AuditActionType 一致:1 提交 / 6 审核通过 / 7 驳回 / 8 物化入库
const ACTION_OPTIONS = [
  { value: 1, label: '提交' },
  { value: 6, label: '审核通过' },
  { value: 7, label: '驳回' },
  { value: 8, label: '物化入库' }
]

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  achievementKind: undefined,
  actionType: undefined,
  operatorKeyword: undefined,
  createTime: undefined
})

const queryFormRef = ref()

const kindLabel = (v: string) => KIND_OPTIONS.find((k) => k.value === v)?.label || v || '-'
const kindTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ award: 'primary', patent: 'success', software: 'warning', innovation: 'info' } as const)[v] ||
  'danger'
const actionLabel = (v: number) => ACTION_OPTIONS.find((a) => a.value === v)?.label || String(v ?? '-')
const actionTone = (v: number): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ 1: 'info', 6: 'success', 7: 'danger', 8: 'warning' } as const)[String(v)] || 'info'

/** changeDetail 是 JSON 字符串,展开行里美化展示;非法 JSON 原样返回 */
const prettyDetail = (raw: string) => {
  if (!raw) {
    return '-'
  }
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

const getList = async () => {
  loading.value = true
  try {
    const data = await getAuditLogPage(queryParams)
    list.value = data.list
    total.value = data.total
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

onMounted(getList)
</script>

<style scoped>
.detail-label {
  display: inline-block;
  width: 80px;
  color: var(--el-text-color-secondary);
}
.detail-json {
  display: inline-block;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}
</style>
