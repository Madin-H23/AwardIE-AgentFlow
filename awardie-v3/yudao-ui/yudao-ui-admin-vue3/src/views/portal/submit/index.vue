<template>
  <div class="portal-page">
    <el-card shadow="never" class="mb-12px">
      <div class="section-title">成果类型</div>
      <el-radio-group v-model="form.achievementType" class="type-group" @change="onTypeChange">
        <el-radio-button v-for="t in TYPES" :key="t.value" :value="t.value">
          {{ t.label }}
        </el-radio-button>
      </el-radio-group>
      <div class="mt-8px text-12px text-gray-500">{{ currentTypeHint }}</div>
    </el-card>

    <el-card shadow="never" class="mb-12px">
      <div class="section-title">证明文件</div>
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".jpg,.jpeg,.png,.pdf"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
      >
        <div v-if="!pickedFile" class="upload-drop">
          <Icon icon="ep:upload-filled" :size="34" class="text-gray-400" />
          <div class="text-12px text-gray-500">拍照或选择奖状/证书图片</div>
          <div class="text-11px text-gray-400">支持 jpg / jpeg / png / pdf,单个 ≤10MB</div>
        </div>
        <div v-else class="picked-file">
          <Icon icon="ep:document-checked" :size="20" />
          <span class="pick-name">{{ pickedFile.name }}</span>
          <el-button link type="danger" @click.stop="onFileRemove">移除</el-button>
        </div>
      </el-upload>
    </el-card>

    <el-card shadow="never" class="mb-12px">
      <div class="section-title">成果信息</div>
      <el-form :model="form" label-position="top">
        <el-form-item
          v-for="field in currentTypeFields"
          :key="field.key"
          :label="field.label"
          :required="field.required"
        >
          <el-input
            v-if="field.multiline"
            v-model="form.data[field.key]"
            type="textarea"
            :rows="3"
            :placeholder="field.placeholder || `请输入${field.label}`"
          />
          <el-input
            v-else
            v-model="form.data[field.key]"
            :type="field.type === 'number' ? 'number' : 'text'"
            :placeholder="field.placeholder || `请输入${field.label}`"
            clearable
          />
        </el-form-item>
      </el-form>
    </el-card>

    <el-button
      type="primary"
      size="large"
      class="submit-btn"
      :loading="submitting"
      :disabled="!pickedFile"
      @click="handleSubmit"
    >
      提交
    </el-button>
    <div class="mt-8px text-12px text-gray-500 text-center">
      提交后进入待审核队列,可在「我的提交」查看进度
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { submitPending } from '@/api/business/achievement'

defineOptions({ name: 'PortalSubmit' })

const router = useRouter()
const message = useMessage()

const TYPES = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]

/**
 * 五类成果的动态字段。后端 submit 只接收一个 data(JSON 字符串),不校验字段名,
 * 但字段名要与成果库物化时的列对齐,所以这里按类给出常用字段,不是穷举。
 */
const TYPE_FIELDS: Record<string, any[]> = {
  award: [
    { key: 'competition_name', label: '竞赛名称', required: true },
    { key: 'award_level', label: '获奖等级', required: true },
    { key: 'winner_name', label: '获奖人', required: true },
    { key: 'issuer', label: '颁发单位' },
    { key: 'award_date', label: '获奖日期', placeholder: 'YYYY-MM-DD' },
    { key: 'supervisor_name', label: '指导教师' }
  ],
  patent: [
    { key: 'patent_name', label: '专利名称', required: true },
    { key: 'patent_type', label: '专利类型', required: true },
    { key: 'application_number', label: '申请号' },
    { key: 'patentee', label: '专利权人' },
    { key: 'inventor', label: '发明人' },
    { key: 'application_date', label: '申请日期', placeholder: 'YYYY-MM-DD' }
  ],
  software: [
    { key: 'software_name', label: '软件名称', required: true },
    { key: 'software_version', label: '版本号' },
    { key: 'registration_number', label: '登记号' },
    { key: 'copyright_owner', label: '著作权人' },
    { key: 'registration_date', label: '登记日期', placeholder: 'YYYY-MM-DD' }
  ],
  innovation: [
    { key: 'project_name', label: '项目名称', required: true },
    { key: 'project_no', label: '项目编号' },
    { key: 'project_type', label: '项目类型', required: true, placeholder: '国家级 / 省级 / 院级' },
    { key: 'start_date', label: '起始日期', placeholder: 'YYYY-MM-DD' },
    { key: 'end_date', label: '结束日期', placeholder: 'YYYY-MM-DD' },
    { key: 'supervisors', label: '指导教师' }
  ],
  other: [
    { key: 'file_name', label: '文件名称', required: true },
    { key: 'file_type', label: '文件类型' },
    { key: 'description', label: '说明', multiline: true }
  ]
}

const HINTS: Record<string, string> = {
  award: '上传奖状或获奖证书图片,并填写竞赛与获奖信息',
  patent: '上传专利证书或受理通知书,填写专利号与专利权人',
  software: '上传软著证书,填写软件名称与登记号',
  innovation: '上传立项或结题材料,填写项目编号与类型',
  other: '其他支撑材料(获奖证明、媒体报道等)'
}

const submitting = ref(false)
const pickedFile = ref<File>()

const form = reactive({
  achievementType: 'award',
  data: {} as Record<string, any>
})

const currentTypeFields = computed(() => TYPE_FIELDS[form.achievementType] || [])
const currentTypeHint = computed(() => HINTS[form.achievementType] || '')

const onTypeChange = () => {
  // 切类型要清空已填字段,否则上一类的字段会跟着 data 一起提交
  form.data = {}
  pickedFile.value = undefined
}

const onFileChange = (file: any) => {
  if (file.raw) {
    pickedFile.value = file.raw
  }
}

const onFileRemove = () => {
  pickedFile.value = undefined
}

const handleSubmit = async () => {
  if (!pickedFile.value) {
    message.warning('请先上传证明文件')
    return
  }
  // 必填项在提交前拦一次:后端只校验文件与类型,不校验结构化字段
  const missing = currentTypeFields.value.filter((f) => f.required && !form.data[f.key]?.trim())
  if (missing.length) {
    message.warning(`请填写:${missing.map((f) => f.label).join('、')}`)
    return
  }
  submitting.value = true
  try {
    await submitPending(pickedFile.value, form.achievementType, JSON.stringify(form.data))
    message.success('提交成功,等待审核')
    form.data = {}
    pickedFile.value = undefined
    router.push('/portal/submissions')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.portal-page {
  max-width: 720px;
  margin: 0 auto;
}
.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
}
/* 五类在小屏放不下五个,允许换行而不是横向滚动 */
.type-group {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}
.type-group :deep(.el-radio-button) {
  flex: 1 1 30%;
  min-width: 96px;
}
.type-group :deep(.el-radio-button__inner) {
  width: 100%;
  min-height: 44px;
  line-height: 44px;
  padding: 0 8px;
}
.upload-drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-height: 120px;
  padding: 16px;
  border: 1px dashed var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  cursor: pointer;
}
.picked-file {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
}
.pick-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 触控目标 ≥44px */
.submit-btn {
  width: 100%;
  min-height: 48px;
  font-size: 16px;
}
</style>
