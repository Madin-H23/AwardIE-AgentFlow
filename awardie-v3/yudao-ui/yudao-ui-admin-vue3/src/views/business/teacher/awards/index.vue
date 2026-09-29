<template>
  <ContentWrap>
    <el-alert type="info" :closable="false" class="mb-12px">
      <template #title>
        范围:指导教师含「{{ myName || '未取到当前用户' }}」的获奖记录,以及本人作为获奖人的教师证书。
        服务端按教师过滤(批16 修复:此前为全量拉取前端筛,越权可读)。
      </template>
    </el-alert>

    <el-form
      ref="queryFormRef"
      :model="queryParams"
      :inline="true"
      label-width="70px"
      class="-mb-20px"
    >
      <el-form-item label="年份" prop="year">
        <el-input
          v-model.number="queryParams.year"
          placeholder="如 2025"
          style="width: 120px"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="按竞赛名称模糊搜索"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="ep:search" @click="handleQuery">搜索</el-button>
        <el-button icon="ep:refresh" @click="resetQuery">重置</el-button>
        <el-button :loading="exporting" icon="ep:download" @click="handleExport">导出 CSV</el-button>
      </el-form-item>
    </el-form>
  </ContentWrap>

  <ContentWrap>
    <div class="mb-10px flex items-center justify-between">
      <span class="text-14px">共 {{ allRows.length }} 条我的成果(指导 {{ supCount }} + 获奖 {{ winCount }})</span>
      <el-button :loading="loading" @click="getList">
        <Icon icon="ep:refresh" class="mr-5px" />刷新
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredRows"
      row-key="id"
      border
      :empty-text="emptyHint"
    >
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="竞赛名称" prop="competition" min-width="240" show-overflow-tooltip />
      <el-table-column label="奖项" prop="awardLevel" width="110" align="center">
        <template #default="scope">{{ scope.row.awardLevel || '-' }}</template>
      </el-table-column>
      <el-table-column label="获奖人" prop="winnerName" min-width="140" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.winnerName || '-' }}</template>
      </el-table-column>
      <el-table-column label="指导教师" prop="supervisorName" min-width="150" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.supervisorName || '-' }}</template>
      </el-table-column>
      <el-table-column label="年份" prop="year" width="90" align="center">
        <template #default="scope">{{ scope.row.year ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="我的身份" width="110" align="center">
        <template #default="scope">
          <el-tag size="small" :type="scope.row.role === '指导' ? 'primary' : 'success'">
            {{ scope.row.role }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </ContentWrap>
</template>

<script setup lang="ts">
/**
 * 教师指导成果(批16 重写):数据源从「vault 全量 + 前端姓名筛」改为
 * /business/teacher/achievements/my 服务端过滤 —— 批9 前置债 D-04 的落点:
 * 原实现把全租户获奖记录拉到浏览器再筛,教师绕过 UI 可读全租户。
 * 关系口径 = v1 文本匹配(supervisor_name/winner_name 含教师名),不依赖关系表。
 */
import { getMyTeacherAchievements, exportMyAchievementsCsv } from '@/api/business/achievement'
import { useUserStore } from '@/store/modules/user'

defineOptions({ name: 'TeacherAwards' })

const message = useMessage()
const userStore = useUserStore()
const myName = computed(() => userStore.getUser?.nickname || '')

const loading = ref(false)
const exporting = ref(false)
const allRows = ref<any[]>([])

const queryParams = reactive({
  year: undefined as number | undefined,
  keyword: undefined
})

const queryFormRef = ref()

const supCount = computed(() => allRows.value.filter((r) => String(r.role).includes('指导')).length)
const winCount = computed(() => allRows.value.filter((r) => String(r.role).includes('获奖')).length)

const emptyHint = computed(() => {
  if (!myName.value) {
    return '取不到当前用户姓名'
  }
  return '没有指导教师含本人姓名的获奖记录,也没有本人作为获奖人的教师证书'
})

/** 前端只做竞赛名关键词过滤(年份过滤在服务端) */
const filteredRows = computed(() => {
  const kw = (queryParams.keyword || '').trim()
  return kw ? allRows.value.filter((r) => (r.competition || '').includes(kw)) : allRows.value
})

const getList = async () => {
  loading.value = true
  try {
    allRows.value = (await getMyTeacherAchievements(queryParams.year)) || []
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  // 年份在服务端;关键词纯前端,两者共用 getList
  getList()
}

const resetQuery = () => {
  queryFormRef.value?.resetFields()
  getList()
}

const handleExport = async () => {
  exporting.value = true
  try {
    const data = await exportMyAchievementsCsv(queryParams.year)
    download0(data, `my-achievements-${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv;charset=UTF-8')
    message.success('导出成功')
  } finally {
    exporting.value = false
  }
}

/** CSV blob 下载(与数据导出页同款) */
const download0 = (data: Blob, fileName: string, mimeType: string) => {
  const blob = new Blob([data], { type: mimeType })
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(href)
}

onMounted(getList)
</script>
