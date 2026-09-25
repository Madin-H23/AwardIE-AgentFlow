<template>
  <Dialog v-model="dialogVisible" :title="dialogTitle">
    <el-form
      ref="formRef"
      v-loading="formLoading"
      :model="formData"
      :rules="formRules"
      label-width="90px"
    >
      <el-form-item label="实验室名称" prop="name">
        <el-input v-model="formData.name" placeholder="请输入实验室名称" maxlength="100" show-word-limit />
      </el-form-item>
      <el-form-item label="描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="4"
          placeholder="请输入实验室描述"
          maxlength="500"
          show-word-limit
        />
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
import * as LaboratoryApi from '@/api/business/basic'

defineOptions({ name: 'LaboratoriesForm' })

const emit = defineEmits(['success'])

const message = useMessage()

const dialogVisible = ref(false)
const dialogTitle = ref('')
const formLoading = ref(false)
const formRef = ref()

const formData = reactive<any>({
  id: undefined,
  name: '',
  description: ''
})

const formRules = reactive<FormRules>({
  name: [{ required: true, message: '实验室名称不能为空', trigger: 'blur' }]
})

/** 打开弹窗。type 为 update 时必须带 id,否则是新增 */
const open = async (type: string, id?: number) => {
  dialogVisible.value = true
  formLoading.value = false
  formData.id = undefined
  formData.name = ''
  formData.description = ''
  dialogTitle.value = type === 'update' ? '修改实验室' : '新增实验室'

  if (type === 'update' && id !== undefined) {
    formLoading.value = true
    try {
      const data = await LaboratoryApi.getLaboratory(id)
      formData.id = data.id
      formData.name = data.name
      formData.description = data.description
    } finally {
      formLoading.value = false
    }
  }
  // 等弹窗里的表单渲染出来再 reset,否则 resetFields 会作用在未挂载的表单上
  await nextTick()
  formRef.value?.resetFields()
}

defineExpose({ open })

const submitForm = async () => {
  await formRef.value.validate()
  formLoading.value = true
  try {
    if (formData.id) {
      await LaboratoryApi.updateLaboratory(formData)
      message.success('修改成功')
    } else {
      await LaboratoryApi.createLaboratory(formData)
      message.success('新增成功')
    }
    dialogVisible.value = false
    emit('success')
  } finally {
    formLoading.value = false
  }
}
</script>
