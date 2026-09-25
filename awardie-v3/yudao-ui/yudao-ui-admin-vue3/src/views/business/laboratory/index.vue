<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="80px"
      class="-mb-20px"
    >
      <el-form-item label="名称" prop="name">
        <el-input
          v-model="queryParams.name"
          placeholder="请输入实验室名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="创建时间" prop="createTime">
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
    <div class="mb-10px flex justify-between">
      <div class="flex items-center gap-8px">
        <el-button v-hasPermi="['business:laboratories:create']" type="primary" @click="openForm('create')">
          <Icon icon="ep:plus" class="mr-5px" />新增
        </el-button>
        <el-button
          v-hasPermi="['business:laboratories:delete']"
          type="danger"
          :disabled="checkedIds.length === 0"
          @click="handleBatchDelete"
        >
          <Icon icon="ep:delete" class="mr-5px" />批量删除
        </el-button>
      </div>
      <el-button
        v-hasPermi="['business:laboratories:export']"
        :loading="exportLoading"
        @click="handleExport"
      >
        <Icon icon="ep:download" class="mr-5px" />导出 Excel
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="list"
      row-key="id"
      border
      empty-text="暂无实验室"
      @selection-change="handleRowCheckboxChange"
    >
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="名称" prop="name" min-width="180" show-overflow-tooltip />
      <el-table-column label="描述" prop="description" min-width="260" show-overflow-tooltip />
      <el-table-column label="创建时间" prop="createTime" width="180" align="center" :formatter="dateFormatter" />
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="scope">
          <el-button
            v-hasPermi="['business:laboratories:update']"
            link
            type="primary"
            @click="openForm('update', scope.row.id)"
          >
            修改
          </el-button>
          <el-button
            v-hasPermi="['business:laboratories:delete']"
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

  <LaboratoryForm ref="formRef" @success="getList" />
</template>

<script setup lang="ts">
import { dateFormatter } from '@/utils/formatTime'
import download from '@/utils/download'
import * as LaboratoryApi from '@/api/business/basic'
import LaboratoryForm from './LaboratoryForm.vue'

defineOptions({ name: 'Laboratories' })

const message = useMessage()

const loading = ref(false)
const exportLoading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const checkedIds = ref<number[]>([])

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  name: undefined,
  createTime: undefined
})

const queryFormRef = ref()

const getList = async () => {
  loading.value = true
  try {
    const data = await LaboratoryApi.getLaboratoryPage(queryParams)
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
  await LaboratoryApi.deleteLaboratory(id)
  message.success('删除成功')
  // 删的是当前页最后一条时,留在空页比跳回上一页更糟——直接回第一页
  if (list.value.length === 1 && queryParams.pageNo > 1) {
    queryParams.pageNo -= 1
  }
  await getList()
}

const handleRowCheckboxChange = (rows: any[]) => {
  checkedIds.value = rows.map((row) => row.id)
}

const handleBatchDelete = async () => {
  if (checkedIds.value.length === 0) {
    return
  }
  await message.delConfirm(`确认删除选中的 ${checkedIds.value.length} 条实验室记录吗?`)
  await LaboratoryApi.deleteLaboratoryList(checkedIds.value)
  message.success('删除成功')
  queryParams.pageNo = 1
  await getList()
}

const handleExport = async () => {
  exportLoading.value = true
  try {
    // 不传分页参数:后端在 @Valid 之后才把 pageSize 置为 -1,前端传 -1 会被 @Min(1) 拦成 400
    const data = await LaboratoryApi.exportLaboratoryExcel({ name: queryParams.name })
    download.excel(data, 'AwardIE 实验室.xls')
  } finally {
    exportLoading.value = false
  }
}

onMounted(getList)
</script>
