<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-F 对照 v1 admin/competitions/detail.html+edit.html:详情+全字段编辑+删除。
interface Competition {
  id: number
  competitionName: string
  gradeCategory: string | null
  organizer: string | null
  competitionTime: string | null
  officialWebsite: string | null
  briefDescription: string | null
  participantRequirements: string | null
  whiteList: boolean
  watchList: boolean
  isAutoAdded: boolean
  aliasList: string | null
}
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const form = reactive({
  competitionName: '', gradeCategory: '', organizer: '', competitionTime: '',
  officialWebsite: '', briefDescription: '', participantRequirements: '',
  whiteList: false, watchList: false,
})
const loading = ref(true)

async function load() {
  const body = await apiJson('GET', `/api/v2/admin/competitions/${id}`)
  if (body.code !== 0) {
    ElMessage.error(body.message ?? '竞赛不存在')
    return
  }
  const d = body.data
  Object.assign(form, {
    competitionName: d.competitionName, gradeCategory: d.gradeCategory ?? '',
    organizer: d.organizer ?? '', competitionTime: d.competitionTime ?? '',
    officialWebsite: d.officialWebsite ?? '', briefDescription: d.briefDescription ?? '',
    participantRequirements: d.participantRequirements ?? '',
    whiteList: !!d.whiteList, watchList: !!d.watchList,
  })
  loading.value = false
}

async function save() {
  if (!form.competitionName.trim()) {
    ElMessage.warning('竞赛名称必填')
    return
  }
  const body = await apiJson('PUT', `/api/v2/admin/competitions/${id}/detail`, { ...form })
  if (body.code === 0) {
    ElMessage.success('已更新')
    router.push('/admin/competitions')
  } else {
    ElMessage.error(body.message)
  }
}

async function remove() {
  const ok = await ElMessageBox.confirm(
    `确定删除竞赛 ${form.competitionName} 吗?存在关联成果时将拒绝。`, '删除确认', { type: 'warning' },
  ).catch(() => false)
  if (!ok) return
  const body = await apiJson('DELETE', `/api/v2/admin/competitions/${id}`)
  if (body.code === 0) {
    ElMessage.success('已删除')
    router.push('/admin/competitions')
  } else {
    ElMessage.error(body.message)
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>竞赛详情</h1>
      <div>
        <el-button @click="router.push('/admin/competitions')">返回列表</el-button>
        <el-button type="danger" data-testid="comp-delete" @click="remove">删除</el-button>
      </div>
    </div>

    <div class="c-panel pad" style="margin-bottom: 14px">
      <h3 class="blk-title">基本信息</h3>
      <el-form label-width="110px" style="max-width: 640px">
        <el-form-item label="竞赛名称" required>
          <el-input v-model="form.competitionName" />
        </el-form-item>
        <el-form-item label="竞赛等级">
          <el-select v-model="form.gradeCategory" placeholder="请选择" clearable style="width: 200px">
            <el-option v-for="g in ['A类', 'B类', 'C类', '其他']" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="举办时间范围">
          <el-input v-model="form.competitionTime" placeholder="例如: 4-10月 或 每年5月" />
        </el-form-item>
        <el-form-item label="主办单位">
          <el-input v-model="form.organizer" placeholder="例如: 教育部高等教育司" />
        </el-form-item>
        <el-form-item label="官网链接">
          <el-input v-model="form.officialWebsite" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="竞赛简介">
          <el-input v-model="form.briefDescription" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="参赛要求">
          <el-input v-model="form.participantRequirements" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="白名单">
          <el-switch v-model="form.whiteList" />
        </el-form-item>
        <el-form-item label="观察名单">
          <el-switch v-model="form.watchList" />
        </el-form-item>
      </el-form>
      <el-button type="primary" data-testid="comp-save" @click="save">保存</el-button>
    </div>
  </div>
</template>

<style scoped>
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
</style>
