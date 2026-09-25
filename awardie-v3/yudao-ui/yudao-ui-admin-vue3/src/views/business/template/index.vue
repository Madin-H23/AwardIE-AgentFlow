<template>
  <ContentWrap>
    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="90px"
      class="-mb-20px"
    >
      <el-form-item label="竞赛" prop="competitionId">
        <el-select v-model="queryParams.competitionId" placeholder="请选择竞赛" clearable filterable class="w-240px">
          <el-option v-for="c in competitionOptions" :key="c.id" :label="c.competitionName" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="授予角色" prop="grantedRole">
        <el-select v-model="queryParams.grantedRole" placeholder="请选择" clearable class="w-140px">
          <el-option label="学生" value="学生" />
          <el-option label="教师" value="教师" />
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
      <el-button v-hasPermi="['business:templates:create']" type="primary" @click="openForm('create')">
        <Icon icon="ep:plus" class="mr-5px" />新建模板
      </el-button>
      <el-button :loading="loading" @click="getList">
        <Icon icon="ep:refresh" class="mr-5px" />刷新
      </el-button>
    </div>

    <el-table v-loading="loading" :data="list" row-key="id" border empty-text="暂无证书模板">
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="竞赛" prop="competitionName" min-width="200" show-overflow-tooltip />
      <el-table-column label="授予角色" width="110" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.grantedRole === '教师' ? 'warning' : 'primary'" size="small">
            {{ scope.row.grantedRole || '-' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="样本图" width="100" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.hasImage" type="success" size="small">有</el-tag>
          <el-tag v-else type="info" size="small">无</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="关键词" min-width="200" show-overflow-tooltip>
        <template #default="scope">
          <el-tag v-for="(k, i) in scope.row.keywords || []" :key="i" size="small" class="mr-4px">
            {{ k }}
          </el-tag>
          <span v-if="!(scope.row.keywords || []).length">-</span>
        </template>
      </el-table-column>
      <el-table-column label="文本长度" width="130" align="center">
        <template #default="scope">
          <span>{{ scope.row.minLength || 0 }} ~ {{ scope.row.maxLength || '不限' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" prop="createTime" width="180" align="center" :formatter="dateFormatter" />
      <el-table-column label="操作" width="240" align="center" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openDetail(scope.row)">查看</el-button>
          <el-button
            v-hasPermi="['business:templates:update']"
            link
            type="primary"
            @click="openForm('update', scope.row)"
          >
            修改
          </el-button>
          <el-button
            v-hasPermi="['business:templates:delete']"
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

  <!-- ================= 新建/修改 ================= -->
  <Dialog v-model="formVisible" :title="formId ? '修改证书模板' : '新建证书模板'" width="760px">
    <el-form :model="formData" label-width="110px">
      <el-form-item v-if="!formId" label="竞赛" required>
        <el-select v-model="formData.competitionId" placeholder="请选择竞赛" filterable class="w-100%">
          <el-option
            v-for="c in competitionOptions"
            :key="c.id"
            :label="c.competitionName"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item v-if="!formId" label="授予角色" required>
        <el-radio-group v-model="formData.grantedRole">
          <el-radio value="学生">学生</el-radio>
          <el-radio value="教师">教师</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="!formId" label="样本图" required>
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".jpg,.jpeg,.png,.pdf"
          :on-change="onSampleChange"
          :on-remove="onSampleRemove"
        >
          <el-button v-if="!sampleFile">
            <Icon icon="ep:upload" class="mr-5px" />选择文件
          </el-button>
          <el-tag v-else closable type="info" @close="onSampleRemove">
            {{ sampleFile.name }}
          </el-tag>
        </el-upload>
        <div class="mt-4px text-12px text-gray-500">
          支持 jpg/jpeg/png/pdf,≤10MB;样本图用于 AI 试测与抽取规则验证
        </div>
      </el-form-item>

      <el-form-item v-if="!formId" label="AI 预抽取">
        <el-button
          :loading="extracting"
          :disabled="!sampleFile"
          @click="handleExtract"
        >
          <Icon icon="ep:magic-stick" class="mr-5px" />上传前先试抽
        </el-button>
        <span class="ml-8px text-12px text-gray-500">
          用当前规则抽一遍样本图,不落库,只帮你把规则调对
        </span>
      </el-form-item>

      <template v-if="extractResult">
        <el-form-item label="AI 模式">
          <el-tag :type="extractResult.mode === 'grpc' ? 'success' : 'info'">
            {{ extractResult.mode === 'grpc' ? '真实 Worker' : '桩模式(fake)' }}
          </el-tag>
          <span class="ml-8px text-12px text-gray-500">{{ extractResult.disclaimer }}</span>
        </el-form-item>
        <el-form-item label="OCR 文本">
          <el-input
            v-model="formData.sampleText"
            type="textarea"
            :rows="4"
            placeholder="试抽出的 OCR 文本,可直接编辑"
          />
        </el-form-item>
        <el-form-item label="抽取结果">
          <pre class="ai-json">{{ prettyJson(formData.sampleExtracted) }}</pre>
        </el-form-item>
      </template>

      <el-form-item label="关键词">
        <el-select
          v-model="formData.keywords"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="回车新增,用于识别竞赛名"
          class="w-100%"
        />
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="最小长度">
            <el-input-number v-model="formData.minLength" :min="0" class="w-100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="最大长度">
            <el-input-number v-model="formData.maxLength" :min="0" class="w-100%" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="输出语言">
        <el-input v-model="formData.language" placeholder="如 zh / en,留空用后端默认" maxlength="10" />
      </el-form-item>
      <el-form-item label="需要翻译">
        <el-switch v-model="formData.needTranslate" />
      </el-form-item>
      <el-form-item label="生成 prompt">
        <el-button :loading="prompting" @click="handleGeneratePrompt">
          <Icon icon="ep:document" class="mr-5px" />生成抽取 prompt
        </el-button>
      </el-form-item>
      <el-form-item v-if="promptResult" label="Prompt">
        <el-input :model-value="promptResult" type="textarea" :rows="8" readonly />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="formLoading" @click="submitForm">确 定</el-button>
      <el-button @click="formVisible = false">取 消</el-button>
    </template>
  </Dialog>

  <!-- ================= 查看 ================= -->
  <el-drawer v-model="detailVisible" title="证书模板详情" size="640px">
    <div v-if="detail" v-loading="detailLoading">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="竞赛">{{ detail.competitionName || detail.competitionId }}</el-descriptions-item>
        <el-descriptions-item label="授予角色">{{ detail.grantedRole || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板类型">{{ detail.templateType || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关键词">
          {{ (detail.keywords || []).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="文本长度">
          {{ detail.minLength || 0 }} ~ {{ detail.maxLength || '不限' }}
        </el-descriptions-item>
        <el-descriptions-item label="样本文本">
          <pre class="ai-json">{{ detail.sampleText || '-' }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="样本抽取">
          <pre class="ai-json">{{ prettyJson(detail.sampleExtracted) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="默认字段">
          <pre class="ai-json">{{ prettyJson(detail.defaultFields) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="LLM 字段">
          <pre class="ai-json">{{ prettyJson(detail.llmFields) }}</pre>
        </el-descriptions-item>
      </el-descriptions>

      <div class="section-title">样本图</div>
      <div v-loading="imgLoading" class="mb-12px">
        <img v-if="imgUrl" :src="imgUrl" class="file-preview" alt="模板样本图" />
        <el-empty v-else-if="imgFailed || !detail.hasImage" description="没有样本图" :image-size="60" />
        <el-skeleton v-else :rows="3" animated />
      </div>

      <div class="section-title">AI 试测</div>
      <el-button :loading="testing" :disabled="!detail.hasImage" @click="handleTest">
        <Icon icon="ep:magic-stick" class="mr-5px" />按当前样本图试抽
      </el-button>
      <template v-if="testResult">
        <el-alert
          class="mt-8px"
          :title="`AI 模式:${testResult.mode === 'grpc' ? '真实 Worker' : '桩模式(fake)'}`"
          :type="testResult.mode === 'grpc' ? 'success' : 'info'"
          :closable="false"
        />
        <p class="mt-4px text-12px text-gray-500">{{ testResult.disclaimer }}</p>
        <div class="section-title">OCR 文本</div>
        <pre class="ai-json">{{ testResult.ocrText || '-' }}</pre>
        <div class="section-title">结构化结果</div>
        <pre class="ai-json">{{ testResult.dataJson }}</pre>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { dateFormatter } from '@/utils/formatTime'
import {
  createTemplate,
  deleteTemplate,
  extractForCreate,
  generatePrompt,
  getTemplate,
  getTemplateImageBlob,
  getTemplatePage,
  testTemplate,
  updateTemplate
} from '@/api/business'
import { getCompetitionPage } from '@/api/business/basic'
import { useBlobUrl } from '../components/useBlobUrl'

defineOptions({ name: 'Template' })

const message = useMessage()

const prettyJson = (v: any) => {
  if (v === null || v === undefined || v === '') {
    return '-'
  }
  try {
    return JSON.stringify(typeof v === 'string' ? JSON.parse(v) : v, null, 2)
  } catch {
    return String(v)
  }
}

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const competitionOptions = ref<any[]>([])

const queryParams = reactive({
  pageNo: 1,
  pageSize: 10,
  competitionId: undefined,
  grantedRole: undefined
})

const queryFormRef = ref()

/** 竞赛下拉要全量,单页 100 足够;后端竞赛分页 pageSize 上限 200 */
const loadCompetitions = async () => {
  const res = await getCompetitionPage({ pageNo: 1, pageSize: 100 })
  competitionOptions.value = res.list || []
}

const getList = async () => {
  loading.value = true
  try {
    const data = await getTemplatePage(queryParams)
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

const handleDelete = async (id: number) => {
  await message.delConfirm()
  await deleteTemplate(id)
  message.success('删除成功')
  if (list.value.length === 1 && queryParams.pageNo > 1) {
    queryParams.pageNo -= 1
  }
  await getList()
}

// ---------------- 新建/修改 ----------------
const formVisible = ref(false)
const formLoading = ref(false)
const formId = ref<number>()
const sampleFile = ref<File>()
const extracting = ref(false)
const prompting = ref(false)
const extractResult = ref<any>()
const promptResult = ref('')

const formData = reactive<any>({
  competitionId: undefined,
  grantedRole: '学生',
  keywords: [],
  minLength: 0,
  maxLength: 0,
  sampleText: '',
  sampleExtracted: {},
  defaultFields: {},
  llmFields: {},
  language: '',
  needTranslate: false
})

const openForm = (type: string, row?: any) => {
  formId.value = type === 'update' ? row.id : undefined
  sampleFile.value = undefined
  extractResult.value = undefined
  promptResult.value = ''
  Object.assign(formData, {
    competitionId: undefined,
    grantedRole: '学生',
    keywords: [],
    minLength: 0,
    maxLength: 0,
    sampleText: '',
    sampleExtracted: {},
    defaultFields: {},
    llmFields: {},
    language: '',
    needTranslate: false
  })
  if (type === 'update' && row) {
    // update 端点只收规则字段,不含 competitionId / grantedRole / 样本图
    Object.assign(formData, {
      keywords: row.keywords || [],
      minLength: row.minLength || 0,
      maxLength: row.maxLength || 0,
      sampleText: row.sampleText || '',
      sampleExtracted: row.sampleExtracted || {},
      defaultFields: row.defaultFields || {},
      llmFields: row.llmFields || {},
      language: row.language || '',
      needTranslate: row.needTranslate === true || row.needTranslate === 1
    })
  }
  formVisible.value = true
}

const onSampleChange = (file: any) => {
  if (file.raw) {
    sampleFile.value = file.raw
    extractResult.value = undefined
  }
}

const onSampleRemove = () => {
  sampleFile.value = undefined
  extractResult.value = undefined
}

const handleExtract = async () => {
  if (!sampleFile.value) {
    return
  }
  extracting.value = true
  try {
    const res = await extractForCreate(sampleFile.value, JSON.stringify(formData.keywords ? { keywords: formData.keywords } : {}))
    extractResult.value = res
    formData.sampleText = res.ocrText || ''
    // dataJson 是 JSON 字符串,后端不做解析
    try {
      formData.sampleExtracted = JSON.parse(res.dataJson || '{}')
    } catch {
      formData.sampleExtracted = { 原始内容: res.dataJson }
    }
  } finally {
    extracting.value = false
  }
}

const handleGeneratePrompt = async () => {
  prompting.value = true
  try {
    const res = await generatePrompt({
      ruleJson: JSON.stringify({ keywords: formData.keywords }),
      sampleText: formData.sampleText
    })
    promptResult.value = res.prompt || ''
  } finally {
    prompting.value = false
  }
}

const submitForm = async () => {
  if (!formId.value) {
    if (!formData.competitionId) {
      message.warning('请选择竞赛')
      return
    }
    if (!sampleFile.value) {
      message.warning('请选择样本图')
      return
    }
  }
  formLoading.value = true
  try {
    if (formId.value) {
      await updateTemplate(formId.value, formData)
      message.success('修改成功')
    } else {
      await createTemplate(sampleFile.value as File, formData)
      message.success('新建成功')
    }
    formVisible.value = false
    await getList()
  } finally {
    formLoading.value = false
  }
}

// ---------------- 查看 ----------------
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>()
const testing = ref(false)
const testResult = ref<any>()

const { url: imgUrl, loading: imgLoading, failed: imgFailed, load: loadImage, revoke: revokeImage } =
  useBlobUrl(getTemplateImageBlob)

const openDetail = async (row: any) => {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = row
  testResult.value = undefined
  try {
    detail.value = await getTemplate(row.id)
  } finally {
    detailLoading.value = false
  }
  revokeImage()
  if (row.hasImage) {
    loadImage(row.id)
  }
}

const handleTest = async () => {
  testing.value = true
  try {
    testResult.value = await testTemplate(detail.value.id)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadCompetitions()
  getList()
})
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
  max-height: 400px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.ai-json {
  width: 100%;
  max-height: 220px;
  margin: 0;
  padding: 8px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  font-size: 12px;
}
</style>
