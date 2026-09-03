<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-T 对照 v1 admin/software/edit.html+view.html(view 字段为子集并入);证书文件挂账(01-方案)。
interface Lab { id: number; name: string }
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const loading = ref(true)
const form = reactive({
  softwareName: '', softwareVersion: '', registrationNumber: '',
  certificateNo: '', registrationDate: '', copyrightOwner: '', laboratoryId: null as number | null,
})
const laboratories = ref<Lab[]>([])
const certificateFile = ref('')
const sys = reactive({ submitterType: '', submitterId: null as number | null, submitTime: '' })

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/software/${id}/edit-detail`)
  if (body.code !== 0) {
    ElMessage.error(body.message ?? '软著不存在')
    loading.value = false
    return
  }
  const d = body.data
  Object.assign(form, {
    softwareName: d.softwareName ?? '', softwareVersion: d.softwareVersion ?? '',
    registrationNumber: d.registrationNumber ?? '', certificateNo: d.certificateNo ?? '',
    registrationDate: d.registrationDate ?? '', copyrightOwner: d.copyrightOwner ?? '',
    laboratoryId: d.laboratoryId,
  })
  laboratories.value = d.laboratories
  certificateFile.value = d.certificateFile ?? ''
  Object.assign(sys, {
    submitterType: d.submitterType ?? '', submitterId: d.submitterId, submitTime: d.submitTime ?? '',
  })
  loading.value = false
})

async function save() {
  if (!form.softwareName.trim()) {
    ElMessage.warning('软件名称必填')
    return
  }
  const body = await apiJson('PUT', `/api/v2/admin/software/${id}`, { ...form })
  if (body.code === 0) {
    ElMessage.success('已更新')
    router.push('/admin/achievements')
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>软著详情/编辑 #{{ id }}</h1>
      <div>
        <el-button type="primary" data-testid="software-edit-save" @click="save">保存</el-button>
        <el-button @click="router.push('/admin/achievements')">返回列表</el-button>
      </div>
    </div>

    <div class="c-panel pad" style="max-width: 640px">
      <h3 class="blk-title">软件著作权信息</h3>
      <div class="frm">
        <label>软件名称 <span class="req">*</span></label>
        <el-input v-model="form.softwareName" data-testid="software-edit-name" />
        <label>版本号</label>
        <el-input v-model="form.softwareVersion" />
        <label>登记号</label>
        <el-input v-model="form.registrationNumber" />
        <label>证书号</label>
        <el-input v-model="form.certificateNo" />
        <label>登记日期</label>
        <el-input v-model="form.registrationDate" placeholder="YYYY-MM-DD" />
        <label>著作权人</label>
        <el-input v-model="form.copyrightOwner" />
        <label>关联实验室</label>
        <el-select v-model="form.laboratoryId" clearable>
          <el-option v-for="l in laboratories" :key="l.id" :value="l.id" :label="l.name" />
        </el-select>
        <label>证书文件</label>
        <p class="muted small">{{ certificateFile ? certificateFile : '无' }}(挂账:文件存储迁移后开放上传/下载)</p>
      </div>
    </div>

    <div class="c-panel pad sys">
      <h3 class="blk-title">系统信息</h3>
      <p class="muted small">提交人类型:{{ sys.submitterType || '-' }} · 提交人ID:{{ sys.submitterId ?? '-' }} · 提交时间:{{ String(sys.submitTime).slice(0, 19).replace('T', ' ') || '-' }}</p>
    </div>
  </div>
</template>

<style scoped>
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.frm { display: flex; flex-direction: column; gap: 6px; }
.frm label { font-size: 0.82rem; color: var(--ink-2); }
.req { color: #ef4444; }
.muted { color: var(--ink-2); }
.small { font-size: 0.78rem; }
.sys { max-width: 640px; margin-top: 14px; }
</style>
