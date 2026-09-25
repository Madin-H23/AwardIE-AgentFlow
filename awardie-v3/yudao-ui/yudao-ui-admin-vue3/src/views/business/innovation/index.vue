<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="80px"
      class="-mb-20px"
    >
      <el-form-item label="项目名称" prop="projectName">
        <el-input
          v-model="queryParams.projectName"
          placeholder="请输入项目名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="项目类型" prop="projectType">
        <el-select v-model="queryParams.projectType" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="t in PROJECT_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="请选择" clearable class="w-140px">
          <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <div class="mb-10px flex flex-wrap items-center justify-between gap-8px">
      <div class="flex flex-wrap items-center gap-8px">
        <el-button v-hasPermi="['business:innovation:import']" type="primary" @click="openImport">
          <Icon icon="ep:upload" class="mr-5px" />导入 xlsx
        </el-button>
        <el-button
          v-hasPermi="['business:innovation:calibrate']"
          type="warning"
          :loading="calibrating"
          @click="handleCalibrate"
        >
          <Icon icon="ep:refresh" class="mr-5px" />校准状态
        </el-button>
      </div>
      <span class="text-12px text-gray-500">共 {{ total }} 个项目</span>
    </div>

    <el-table v-loading="loading" :data="list" row-key="id" border empty-text="暂无大创项目">
      <el-table-column type="expand">
        <template #default="scope">
          <div class="px-12px py-8px">
            <p><span class="detail-label">项目编号:</span>{{ scope.row.projectNo || '-' }}</p>
            <p>
              <span class="detail-label">其他成员:</span>
              <template v-if="(scope.row.otherMembers || []).length">
                <el-tag
                  v-for="(m, i) in scope.row.otherMembers"
                  :key="i"
                  size="small"
                  class="mr-4px"
                >
                  {{ m['姓名'] || m.name || '-' }}
                  <template v-if="m['学号'] || m.id">（{{ m['学号'] || m.id }}）</template>
                </el-tag>
              </template>
              <template v-else>-</template>
            </p>
            <p class="mb-0">
              <span class="detail-label">指导教师:</span>{{ scope.row.supervisors || '-' }}
            </p>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="项目名称" prop="projectName" min-width="220" show-overflow-tooltip />
      <el-table-column label="类型" prop="projectType" width="100" align="center">
        <template #default="scope">
          <el-tag :type="typeTone(scope.row.projectType)" size="small">{{ scope.row.projectType || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="负责人" prop="studentLeaderName" min-width="120" show-overflow-tooltip />
      <el-table-column label="起止" min-width="200" align="center">
        <template #default="scope">
          <span>{{ scope.row.startDate || '-' }} ~ {{ scope.row.endDate || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="经费(元)" prop="fundingAmount" width="130" align="right">
        <template #default="scope">
          <span>{{ scope.row.fundingAmount ?? 0 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="scope">
          <el-tag :type="statusTone(scope.row.status)" size="small">{{ scope.row.status || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="scope">
          <el-button
            v-hasPermi="['business:innovation:update']"
            link
            type="primary"
            @click="openForm(scope.row)"
          >
            修改
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

  <!-- 行编辑:大创没有新建入口(只能由导入通道产生),所以只做修改 -->
  <Dialog v-model="formVisible" title="修改大创项目" width="640px">
    <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
      <el-form-item label="项目编号" prop="projectNo">
        <el-input v-model="formData.projectNo" placeholder="如 DC-2025-001" maxlength="50" />
      </el-form-item>
      <el-form-item label="项目名称" prop="projectName">
        <el-input v-model="formData.projectName" placeholder="请输入项目名称" maxlength="200" />
      </el-form-item>
      <el-form-item label="项目类型" prop="projectType">
        <el-select v-model="formData.projectType" placeholder="请选择" class="w-100%">
          <el-option v-for="t in PROJECT_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="formData.status" placeholder="请选择" class="w-100%">
          <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="起始日期" prop="startDate">
        <el-input v-model="formData.startDate" placeholder="YYYY-MM-DD" maxlength="10" />
      </el-form-item>
      <el-form-item label="结束日期" prop="endDate">
        <el-input v-model="formData.endDate" placeholder="YYYY-MM-DD" maxlength="10" />
      </el-form-item>
      <el-form-item label="负责人" prop="studentLeaderName">
        <el-input v-model="formData.studentLeaderName" placeholder="姓名" maxlength="50" />
      </el-form-item>
      <el-form-item label="负责人学号" prop="studentLeaderId">
        <el-input v-model="formData.studentLeaderId" placeholder="学号" maxlength="50" />
      </el-form-item>
      <el-form-item label="指导教师" prop="supervisors">
        <el-input v-model="formData.supervisors" placeholder="多人用逗号分隔" />
      </el-form-item>
      <el-form-item label="经费(元)" prop="fundingAmount">
        <el-input-number v-model="formData.fundingAmount" :min="0" :precision="2" class="w-100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="formLoading" @click="submitForm">确 定</el-button>
      <el-button @click="formVisible = false">取 消</el-button>
    </template>
  </Dialog>

  <!-- 导入:先预览,确认 token 后才落库(token 单次有效) -->
  <Dialog v-model="importVisible" title="大创项目 xlsx 导入" width="880px">
    <el-alert type="info" :closable="false" class="mb-12px">
      <template #title>
        表头必须严格为:项目编号, 项目名称, 项目类型, 起始日期, 结束日期, 负责人姓名, 负责人学号,
        其他成员, 指导教师, 经费(顺序、个数、名称全一致);项目类型限「国家级/省级/院级」;
        经费按<strong>万元</strong>填,系统自动 ×10000 存为元;最多 1000 行。
      </template>
    </el-alert>

    <el-upload
      v-if="!preview"
      drag
      :auto-upload="false"
      :limit="1"
      accept=".xlsx"
      :on-change="onFileChange"
      :on-remove="onFileRemove"
    >
      <Icon icon="ep:upload-filled" :size="40" class="text-gray-400" />
      <div class="el-upload__text">将 .xlsx 拖到此处,或<em>点击选择</em></div>
    </el-upload>

    <template v-else>
      <div class="mb-8px flex items-center gap-12px">
        <el-tag type="info">共 {{ preview.rowCount }} 行</el-tag>
        <el-tag :type="preview.errorCount > 0 ? 'danger' : 'success'">
          {{ preview.errorCount > 0 ? `${preview.errorCount} 行有错` : '全部校验通过' }}
        </el-tag>
        <el-button link type="primary" @click="preview = undefined">重新选文件</el-button>
      </div>
      <el-table :data="preview.rows" border max-height="360" empty-text="没有可导入的行">
        <el-table-column label="行号" prop="rowNo" width="70" align="center" />
        <el-table-column label="项目编号" prop="projectNo" min-width="120" show-overflow-tooltip />
        <el-table-column label="项目名称" prop="projectName" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" prop="projectType" width="90" align="center" />
        <el-table-column label="负责人" prop="leaderName" width="100" />
        <el-table-column label="学号" prop="leaderId" width="110" />
        <el-table-column label="指导教师" prop="supervisors" min-width="140" show-overflow-tooltip />
        <el-table-column label="经费(万元)" prop="funding" width="110" align="right" />
        <el-table-column label="校验" width="180" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.error" type="danger" size="small">{{ scope.row.error }}</el-tag>
            <el-tag v-else type="success" size="small">通过</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <template #footer>
      <template v-if="preview">
        <el-button @click="importVisible = false">取 消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImportConfirm">
          确认导入({{ preview.rowCount - preview.errorCount }} 行)
        </el-button>
      </template>
      <el-button v-else @click="importVisible = false">取 消</el-button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { FormRules } from 'element-plus'

import {
  calibrateInnovationStatus,
  confirmInnovationImport,
  getInnovationPage,
  previewInnovationImport,
  updateInnovation
} from '@/api/business'

defineOptions({ name: 'Innovation' })

const message = useMessage()

const PROJECT_TYPES = ['国家级', '省级', '院级']
const STATUSES = ['进行中', '已结题', '终止']

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  projectName: undefined,
  projectType: undefined,
  status: undefined
})

const queryFormRef = ref()

const typeTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ 国家级: 'danger', 省级: 'warning', 院级: 'info' } as const)[v] || 'info'
const statusTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ 进行中: 'success', 已结题: 'info', 终止: 'danger' } as const)[v] || 'info'

const getList = async () => {
  loading.value = true
  try {
    const data = await getInnovationPage(queryParams)
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

// ---------------- 行编辑 ----------------
const formVisible = ref(false)
const formLoading = ref(false)
const formRef = ref()
const formId = ref<number>()

const formData = reactive<any>({
  projectNo: '',
  projectName: '',
  projectType: '',
  status: '',
  startDate: '',
  endDate: '',
  studentLeaderName: '',
  studentLeaderId: '',
  supervisors: '',
  fundingAmount: 0
})

const formRules = reactive<FormRules>({
  projectName: [{ required: true, message: '项目名称不能为空', trigger: 'blur' }]
})

const openForm = (row: any) => {
  formId.value = row.id
  Object.assign(formData, {
    projectNo: row.projectNo ?? '',
    projectName: row.projectName ?? '',
    projectType: row.projectType ?? '',
    status: row.status ?? '',
    // 后端这两个字段是 String 不是 LocalDate,原样透传不要 new Date()
    startDate: row.startDate ?? '',
    endDate: row.endDate ?? '',
    studentLeaderName: row.studentLeaderName ?? '',
    studentLeaderId: row.studentLeaderId ?? '',
    supervisors: row.supervisors ?? '',
    fundingAmount: Number(row.fundingAmount ?? 0)
  })
  formVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

const submitForm = async () => {
  await formRef.value.validate()
  formLoading.value = true
  try {
    await updateInnovation(formId.value as number, formData)
    message.success('修改成功')
    formVisible.value = false
    await getList()
  } finally {
    formLoading.value = false
  }
}

// ---------------- 导入 ----------------
const importVisible = ref(false)
const importing = ref(false)
const preview = ref<any>()
const pickedFile = ref<File>()

const openImport = () => {
  preview.value = undefined
  pickedFile.value = undefined
  importVisible.value = true
}

const onFileChange = async (file: any) => {
  // el-upload 只在 auto-upload=false 时给 raw,没有 raw 说明是取消选择
  if (!file.raw) {
    return
  }
  pickedFile.value = file.raw
  try {
    preview.value = await previewInnovationImport(file.raw)
  } catch {
    preview.value = undefined
  }
}

const onFileRemove = () => {
  pickedFile.value = undefined
  preview.value = undefined
}

const handleImportConfirm = async () => {
  if (!preview.value) {
    return
  }
  importing.value = true
  try {
    const res = await confirmInnovationImport(preview.value.token)
    message.success(
      `导入 ${res.imported} 条,跳过 ${res.skipped} 条;关联学生 ${res.studentsLinked} 人,未匹配 ${res.studentsUnmatched} 人`
    )
    if (res.errors?.length) {
      message.warning(res.errors.slice(0, 3).join('; ') + (res.errors.length > 3 ? ' …' : ''))
    }
    importVisible.value = false
    preview.value = undefined
    await getList()
  } finally {
    importing.value = false
  }
}

// ---------------- 状态校准 ----------------
const calibrating = ref(false)
const handleCalibrate = async () => {
  await message.confirm(
    '将按结束日期重新推导状态:结束日期严格早于今天的「进行中」项目会被改为「已结题」。继续?',
    '状态校准'
  )
  calibrating.value = true
  try {
    const res = await calibrateInnovationStatus()
    message.success(
      `检查 ${res.considered} 条,校准 ${res.calibrated} 条,无法解析日期跳过 ${res.skippedUnparsed} 条`
    )
    await getList()
  } finally {
    calibrating.value = false
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
</style>
