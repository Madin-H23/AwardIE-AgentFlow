<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="90px"
      class="-mb-20px"
    >
      <el-form-item label="竞赛名称" prop="competitionName">
        <el-input
          v-model="queryParams.competitionName"
          placeholder="请输入竞赛名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="白名单" prop="whiteList">
        <el-select v-model="queryParams.whiteList" placeholder="请选择" clearable class="w-120px">
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="观察名单" prop="watchList">
        <el-select v-model="queryParams.watchList" placeholder="请选择" clearable class="w-120px">
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <div class="mb-10px flex justify-between">
      <el-button v-hasPermi="['business:competitions:create']" type="primary" @click="openForm('create')">
        <Icon icon="ep:plus" class="mr-5px" />新增
      </el-button>
      <el-button
        v-hasPermi="['business:competitions:export']"
        :loading="exportLoading"
        @click="handleExport"
      >
        <Icon icon="ep:download" class="mr-5px" />导出 Excel
      </el-button>
    </div>

    <el-table v-loading="loading" :data="list" row-key="id" border empty-text="暂无竞赛">
      <el-table-column type="expand">
        <template #default="scope">
          <div class="px-12px py-8px">
            <p><span class="detail-label">官网地址:</span>{{ scope.row.officialWebsite || '-' }}</p>
            <p><span class="detail-label">参赛要求:</span>{{ scope.row.participantRequirements || '-' }}</p>
            <p><span class="detail-label">简介:</span>{{ scope.row.briefDescription || '-' }}</p>
            <p class="mb-0">
              <span class="detail-label">别名列表:</span>
              <template v-if="scope.row.aliasList">
                <span
                  v-for="(alias, i) in scope.row.aliasList.split('\n').filter(Boolean)"
                  :key="i"
                  class="alias-chip"
                  >{{ alias.trim() }}</span
                >
              </template>
              <template v-else>-</template>
            </p>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="竞赛名称" prop="competitionName" min-width="220" show-overflow-tooltip />
      <el-table-column label="主办方" prop="organizer" min-width="160" show-overflow-tooltip />
      <el-table-column label="竞赛时间" prop="competitionTime" width="120" align="center" />
      <el-table-column label="组别" prop="gradeCategory" min-width="140" show-overflow-tooltip />
      <el-table-column label="白名单" width="100" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.whiteList ? 'success' : 'info'" size="small">
            {{ scope.row.whiteList ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="观察名单" width="100" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.watchList ? 'warning' : 'info'" size="small">
            {{ scope.row.watchList ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" prop="createTime" width="180" align="center" :formatter="dateFormatter" />
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="scope">
          <el-button
            v-hasPermi="['business:competitions:update']"
            link
            type="primary"
            @click="openForm('update', scope.row.id)"
          >
            修改
          </el-button>
          <el-button
            v-hasPermi="['business:competitions:delete']"
            link
            type="danger"
            @click="handleDelete(scope.row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <Pagination
      v-model:page="queryParams.pageNo"
      v-model:limit="queryParams.pageSize"
      :total="total"
      @pagination="getList"
    />
  </ContentWrap>

  <CompetitionForm ref="formRef" @success="getList" />
</template>

<script setup lang="ts">
import { dateFormatter } from '@/utils/formatTime'
import download from '@/utils/download'
import * as CompetitionApi from '@/api/business/basic'
import CompetitionForm from './CompetitionForm.vue'

defineOptions({ name: 'Competitions' })

const message = useMessage()

const loading = ref(false)
const exportLoading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  competitionName: undefined,
  whiteList: undefined,
  watchList: undefined
})

const queryFormRef = ref()

const getList = async () => {
  loading.value = true
  try {
    const data = await CompetitionApi.getCompetitionPage(queryParams)
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

const formRef = ref()
const openForm = (type: string, id?: number) => {
  formRef.value.open(type, id)
}

const handleDelete = async (id: number) => {
  await message.delConfirm()
  await CompetitionApi.deleteCompetition(id)
  message.success('删除成功')
  if (list.value.length === 1 && queryParams.pageNo > 1) {
    queryParams.pageNo -= 1
  }
  await getList()
}

const handleExport = async () => {
  exportLoading.value = true
  try {
    const data = await CompetitionApi.exportCompetitionExcel({
      competitionName: queryParams.competitionName
    })
    download.excel(data, 'AwardIE 竞赛.xls')
  } finally {
    exportLoading.value = false
  }
}

onMounted(getList)
</script>

<style scoped>
.detail-label {
  display: inline-block;
  width: 80px;
  color: var(--el-text-color-secondary);
}
.alias-chip {
  display: inline-block;
  margin: 0 6px 4px 0;
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  font-size: 12px;
}
</style>
