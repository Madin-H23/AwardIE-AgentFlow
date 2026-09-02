<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-G 对照 v1 laboratories/edit.html:三字段编辑(名称/简介/封面上传挂账——依赖文件存储)。
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const form = reactive({ name: '', description: '' })
const loading = ref(true)

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/laboratories/${id}/detail`)
  if (body.code === 0) {
    form.name = body.data.name
    form.description = body.data.description ?? ''
  } else {
    ElMessage.error(body.message ?? '实验室不存在')
  }
  loading.value = false
})

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('实验室名称必填')
    return
  }
  const body = await apiJson('PUT', `/api/v2/admin/laboratories/${id}`, { ...form })
  if (body.code === 0) {
    ElMessage.success('已更新')
    router.push(`/admin/laboratories/${id}`)
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>编辑实验室</h1>
    </div>
    <div class="c-panel pad" style="max-width: 560px">
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" data-testid="lab-edit-name" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-testid="lab-edit-save" @click="save">保存</el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>
