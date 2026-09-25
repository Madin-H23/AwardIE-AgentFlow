<template>
  <Dialog v-model="dialogVisible" :title="dialogTitle" width="720px">
    <el-form
      ref="formRef"
      v-loading="formLoading"
      :model="formData"
      :rules="formRules"
      label-width="110px"
    >
      <el-form-item label="竞赛名称" prop="competitionName">
        <el-input v-model="formData.competitionName" placeholder="请输入竞赛名称" maxlength="200" show-word-limit />
      </el-form-item>
      <el-form-item label="官网地址" prop="officialWebsite">
        <el-input v-model="formData.officialWebsite" placeholder="请输入官网地址" maxlength="500" />
      </el-form-item>
      <el-form-item label="主办方" prop="organizer">
        <el-input v-model="formData.organizer" placeholder="请输入主办方" maxlength="200" />
      </el-form-item>
      <el-form-item label="竞赛时间" prop="competitionTime">
        <el-input v-model="formData.competitionTime" placeholder="如 4-10月" maxlength="100" />
      </el-form-item>
      <el-form-item label="组别类别" prop="gradeCategory">
        <el-input v-model="formData.gradeCategory" placeholder="请输入组别类别" maxlength="200" />
      </el-form-item>
      <el-form-item label="参赛要求" prop="participantRequirements">
        <el-input
          v-model="formData.participantRequirements"
          type="textarea"
          :rows="3"
          placeholder="请输入参赛要求"
        />
      </el-form-item>
      <el-form-item label="简介" prop="briefDescription">
        <el-input
          v-model="formData.briefDescription"
          type="textarea"
          :rows="3"
          placeholder="请输入竞赛简介"
        />
      </el-form-item>
      <el-form-item label="别名列表" prop="aliasList">
        <el-input
          v-model="formData.aliasList"
          type="textarea"
          :rows="3"
          placeholder="一行一个别名,用于 OCR 抽取时匹配竞赛名"
        />
      </el-form-item>
      <el-form-item label="白名单" prop="whiteList">
        <el-switch v-model="formData.whiteList" />
        <span class="ml-8px text-12px text-gray-500">白名单竞赛在统计中单独计数</span>
      </el-form-item>
      <el-form-item label="观察名单" prop="watchList">
        <el-switch v-model="formData.watchList" />
        <span class="ml-8px text-12px text-gray-500">观察名单竞赛暂不计入白名单统计</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="formLoading" @click="submitForm">确 定</el-button>
      <el-button @click="dialogVisible = false">取 消</el-button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { FormRules } from 'element-plus'
import * as CompetitionApi from '@/api/business/basic'

defineOptions({ name: 'CompetitionsForm' })

const emit = defineEmits(['success'])

const message = useMessage()

const dialogVisible = ref(false)
const dialogTitle = ref('')
const formLoading = ref(false)
const formRef = ref()

const formData = reactive<any>({
  id: undefined,
  competitionName: '',
  officialWebsite: '',
  organizer: '',
  competitionTime: '',
  participantRequirements: '',
  gradeCategory: '',
  briefDescription: '',
  aliasList: '',
  whiteList: false,
  watchList: false
})

const formRules = reactive<FormRules>({
  competitionName: [{ required: true, message: '竞赛名称不能为空', trigger: 'blur' }]
})

/** 打开弹窗。type 为 update 时必须带 id,否则是新增 */
const open = async (type: string, id?: number) => {
  dialogVisible.value = true
  formLoading.value = false
  Object.assign(formData, {
    id: undefined,
    competitionName: '',
    officialWebsite: '',
    organizer: '',
    competitionTime: '',
    participantRequirements: '',
    gradeCategory: '',
    briefDescription: '',
    aliasList: '',
    whiteList: false,
    watchList: false
  })
  dialogTitle.value = type === 'update' ? '修改竞赛' : '新增竞赛'

  if (type === 'update' && id !== undefined) {
    formLoading.value = true
    try {
      const data = await CompetitionApi.getCompetition(id)
      Object.assign(formData, data)
      // 后端白名单/观察名单是 Boolean,库里可能是 0/1,统一成布尔免得 switch 显示错态
      formData.whiteList = data.whiteList === true || data.whiteList === 1
      formData.watchList = data.watchList === true || data.watchList === 1
    } finally {
      formLoading.value = false
    }
  }
  await nextTick()
  formRef.value?.resetFields()
}

defineExpose({ open })

const submitForm = async () => {
  await formRef.value.validate()
  formLoading.value = true
  try {
    if (formData.id) {
      await CompetitionApi.updateCompetition(formData)
      message.success('修改成功')
    } else {
      await CompetitionApi.createCompetition(formData)
      message.success('新增成功')
    }
    dialogVisible.value = false
    emit('success')
  } finally {
    formLoading.value = false
  }
}
</script>
