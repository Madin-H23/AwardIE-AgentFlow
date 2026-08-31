<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

const API = '/api/v2/profile'
const role = ref('')
const fields = ref<string[]>([])
const form = reactive<Record<string, string>>({})

const LABELS: Record<string, string> = {
  name: '姓名', phone: '电话', qq: 'QQ', skills: '技能',
  major: '专业', grade: '年级', title: '职称', department: '所属系',
}

onMounted(async () => {
  const f = await apiJson('GET', `${API}/fields`)
  if (f.code === 0) {
    role.value = f.data.role
    fields.value = f.data.fields
  }
  const me = await apiJson('GET', API)
  if (me.code === 0) {
    for (const k of fields.value) form[k] = (me.data as Record<string, string>)[k] ?? ''
  }
})

async function onSave() {
  const body: Record<string, unknown> = { ...form, profileIsPublic: true }
  for (const k of ['name', 'phone', 'qq', 'skills', 'major', 'grade', 'title', 'department']) {
    if (!fields.value.includes(k)) body[k] = ''
  }
  const resp = await apiJson('PUT', API, body)
  if (resp.code === 0) ElMessage.success('资料已更新')
  else ElMessage.error(resp.message)
}
</script>

<template>
  <div class="profile-page">
    <el-card>
      <h2>个人资料({{ role }})</h2>
      <el-form label-position="top">
        <el-form-item
          v-for="k in fields"
          :key="k"
          :label="LABELS[k] ?? k"
        >
          <el-input
            v-model="form[k]"
            :data-testid="`profile-${k}`"
          />
        </el-form-item>
        <el-button
          type="primary"
          data-testid="profile-save"
          @click="onSave"
        >
          保存
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-page { max-width: 640px; margin: 24px auto; }
h2 { margin-top: 0; color: var(--ink); }
</style>
