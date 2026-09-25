<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="70px"
      class="-mb-20px"
    >
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="按名称模糊搜索"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <el-tabs v-model="activeType" @tab-change="handleTabChange">
      <el-tab-pane v-for="t in TYPES" :key="t.value" :label="t.label" :name="t.value" />
    </el-tabs>

    <el-table
      v-loading="loading"
      :data="list"
      row-key="id"
      border
      :empty-text="`暂无${currentType.label}记录`"
    >
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column
        v-for="col in currentType.columns"
        :key="col.prop"
        :label="col.label"
        :prop="col.prop"
        :min-width="col.width"
        :align="col.align || 'left'"
        :formatter="col.formatter"
        show-overflow-tooltip
      />
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="scope">
          <el-button
            v-hasPermi="['business:vault:update']"
            link
            type="primary"
            @click="openForm(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            v-hasPermi="['business:vault:delete']"
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

  <!--
    行编辑字段是后端 per-type 白名单(VaultSpec.editableColumns):
    白名单外的键会被后端拒掉,所以表单字段必须由配置生成,不能手写全字段表单。
  -->
  <Dialog v-model="formVisible" :title="`编辑${currentType.label}`" width="640px">
    <el-form :model="formData" label-width="110px">
      <el-form-item
        v-for="field in currentType.editable"
        :key="field.key"
        :label="field.label"
        :prop="field.key"
      >
        <el-select v-if="field.options" v-model="formData[field.key]" placeholder="请选择" clearable>
          <el-option v-for="o in field.options" :key="String(o)" :label="o" :value="o" />
        </el-select>
        <el-switch v-else-if="field.boolean" v-model="formData[field.key]" />
        <el-input-number
          v-else-if="field.number"
          v-model="formData[field.key]"
          :min="0"
          :precision="0"
          class="w-100%"
        />
        <el-input v-else v-model="formData[field.key]" :placeholder="`请输入${field.label}`" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="formLoading" @click="submitForm">确 定</el-button>
      <el-button @click="formVisible = false">取 消</el-button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { deleteVaultRow, getVaultPage, updateVaultRow } from '@/api/business/achievement'

defineOptions({ name: 'Vault' })

const message = useMessage()

/** 布尔列在库里是 0/1,直接显示会看到 "0"/"1" */
const boolFormatter = (_r: any, _c: any, v: any) =>
  v === true || v === 1 ? '是' : v === false || v === 0 ? '否' : '-'

/**
 * 五类成果的列与可编辑字段。列集与可编辑白名单都由后端 VaultSpec 决定,
 * 前端只做展示与提交;白名单外的键后端会拒。
 * 注意 name 是列别名(AS name),真名各类不同,编辑时要还原成真列名。
 */
interface VaultField {
  key: string
  label: string
  /** 下拉可选值;有则渲染 select */
  options?: string[]
  /** 布尔列渲染 switch */
  boolean?: boolean
  /** 数字列渲染 input-number(空值提交 null,不能提交 '') */
  number?: boolean
}
interface VaultColumn {
  prop: string
  label: string
  width: number
  align?: 'left' | 'center' | 'right'
  formatter?: (row: any, column: any, value: any) => string
}
interface VaultTypeSpec {
  value: string
  label: string
  /** 展示列里的 name 别名对应的真列名 */
  nameColumn: string
  columns: VaultColumn[]
  editable: VaultField[]
}

const TYPES: VaultTypeSpec[] = [
  {
    value: 'award',
    label: '获奖成果',
    nameColumn: 'competition_name_in_file',
    columns: [
      { prop: 'name', label: '竞赛名称', width: 220 },
      { prop: 'competition_level', label: '获奖等级', width: 110 },
      { prop: 'award_level', label: '奖项', width: 110 },
      { prop: 'winner_name', label: '获奖人', width: 140 },
      { prop: 'supervisor_name', label: '指导教师', width: 150 },
      { prop: 'year', label: '年份', width: 90, align: 'center' },
      {
        prop: 'is_abnormal',
        label: '异常',
        width: 90,
        align: 'center',
        formatter: boolFormatter
      }
    ],
    editable: [
      { key: 'competition_name_in_file', label: '竞赛名称' },
      { key: 'competition_level', label: '获奖等级' },
      { key: 'award_level', label: '奖项' },
      { key: 'winner_name', label: '获奖人' },
      { key: 'supervisor_name', label: '指导教师' },
      { key: 'group_name', label: '组别' },
      { key: 'province', label: '省份' },
      { key: 'year', label: '年份' },
      { key: 'is_abnormal', label: '异常', boolean: true },
      { key: 'laboratory_id', label: '实验室编号', number: true }
    ]
  },
  {
    value: 'patent',
    label: '专利',
    nameColumn: 'patent_name',
    columns: [
      { prop: 'name', label: '专利名称', width: 220 },
      { prop: 'patent_type', label: '专利类型', width: 110 },
      { prop: 'application_number', label: '申请号', width: 150 },
      { prop: 'patentee', label: '专利权人', width: 160 },
      { prop: 'inventor', label: '发明人', width: 150 }
    ],
    editable: [
      { key: 'patent_name', label: '专利名称' },
      { key: 'patent_type', label: '专利类型' },
      { key: 'application_number', label: '申请号' },
      { key: 'publication_number', label: '公开号' },
      { key: 'inventor', label: '发明人' },
      { key: 'patentee', label: '专利权人' },
      { key: 'application_date', label: '申请日期' },
      { key: 'laboratory_id', label: '实验室编号', number: true }
    ]
  },
  {
    value: 'software',
    label: '软件著作权',
    nameColumn: 'software_name',
    columns: [
      { prop: 'name', label: '软件名称', width: 220 },
      { prop: 'software_version', label: '版本号', width: 110 },
      { prop: 'registration_number', label: '登记号', width: 180 },
      { prop: 'copyright_owner', label: '著作权人', width: 160 }
    ],
    editable: [
      { key: 'software_name', label: '软件名称' },
      { key: 'software_version', label: '版本号' },
      { key: 'registration_number', label: '登记号' },
      { key: 'certificate_no', label: '证书号' },
      { key: 'copyright_owner', label: '著作权人' },
      { key: 'registration_date', label: '登记日期' },
      { key: 'laboratory_id', label: '实验室编号', number: true }
    ]
  },
  {
    value: 'innovation',
    label: '大创项目',
    nameColumn: 'project_name',
    columns: [
      { prop: 'project_no', label: '项目编号', width: 130 },
      { prop: 'name', label: '项目名称', width: 200 },
      { prop: 'project_type', label: '类型', width: 90 },
      { prop: 'student_leader_name', label: '负责人', width: 110 },
      { prop: 'supervisors', label: '指导教师', width: 150 },
      { prop: 'status', label: '状态', width: 100 }
    ],
    editable: [
      { key: 'project_name', label: '项目名称' },
      { key: 'project_type', label: '项目类型', options: ['国家级', '省级', '院级'] },
      { key: 'start_date', label: '开始日期' },
      { key: 'end_date', label: '结束日期' },
      { key: 'student_leader_name', label: '负责人' },
      { key: 'supervisors', label: '指导教师' },
      { key: 'status', label: '状态', options: ['进行中', '已结题', '终止'] },
      { key: 'laboratory_id', label: '实验室编号', number: true }
    ]
  },
  {
    value: 'other',
    label: '其他文件',
    nameColumn: 'file_name',
    columns: [
      { prop: 'name', label: '文件名', width: 240 },
      { prop: 'file_type', label: '类型', width: 110 },
      { prop: 'file_size', label: '大小', width: 110, align: 'right' },
      { prop: 'description', label: '说明', width: 200 }
    ],
    editable: [
      { key: 'file_name', label: '文件名' },
      { key: 'description', label: '说明' },
      { key: 'laboratory_id', label: '实验室编号', number: true }
    ]
  }
]

const activeType = ref<string>('award')
const currentType = computed(() => TYPES.find((t) => t.value === activeType.value) || TYPES[0])

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const queryParams = reactive({
  pageNo: 1,
  pageSize: 20,
  keyword: undefined
})

const queryFormRef = ref()

const getList = async () => {
  loading.value = true
  try {
    // 该端点不走 PageParam,pageSize 后端夹在 1..100,默认 20
    const data = await getVaultPage(activeType.value, queryParams)
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

const handleTabChange = () => {
  queryParams.pageNo = 1
  getList()
}

const handleDelete = async (id: number) => {
  await message.delConfirm()
  await deleteVaultRow(activeType.value, id)
  message.success('删除成功')
  if (list.value.length === 1 && queryParams.pageNo > 1) {
    queryParams.pageNo -= 1
  }
  await getList()
}

// ---------------- 行编辑 ----------------
const formVisible = ref(false)
const formLoading = ref(false)
const formId = ref<number>()
const formData = reactive<Record<string, any>>({})

const openForm = (row: any) => {
  formId.value = row.id
  // 只取当前类型的白名单字段,并把 name 别名还原成真列名
  for (const f of currentType.value.editable) {
    if (f.key === currentType.value.nameColumn) {
      formData[f.key] = row.name ?? ''
    } else if (f.boolean) {
      formData[f.key] = row[f.key] === true || row[f.key] === 1
    } else if (f.number) {
      formData[f.key] = row[f.key] ?? undefined
    } else {
      formData[f.key] = row[f.key] ?? ''
    }
  }
  formVisible.value = true
}

const submitForm = async () => {
  // 空字符串会让后端把可空列写成 '' 而不是 NULL;数字列传 '' 会直接 400
  const payload: Record<string, any> = {}
  for (const f of currentType.value.editable) {
    const v = formData[f.key]
    if (f.number) {
      payload[f.key] = v === '' || v === null || v === undefined ? null : Number(v)
    } else {
      payload[f.key] = v === '' ? null : v
    }
  }
  formLoading.value = true
  try {
    await updateVaultRow(activeType.value, formId.value as number, payload)
    message.success('保存成功')
    formVisible.value = false
    await getList()
  } finally {
    formLoading.value = false
  }
}

onMounted(getList)
</script>
