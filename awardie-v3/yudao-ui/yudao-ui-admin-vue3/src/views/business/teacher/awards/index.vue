<template>
  <ContentWrap>
    <el-alert
      type="info"
      :closable="false"
      class="mb-12px"
    >
      <template #title>
        按指导教师姓名「{{ myName || '未取到当前用户' }}」匹配。v3 目前没有教师关系表
        (批9 遗留的前置债),所以这里是从全部获奖记录里筛出指导教师含本人姓名的行;
        指导教师字段为空的记录不会出现在本页。
      </template>
    </el-alert>

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
          placeholder="按竞赛名称模糊搜索"
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
    <div class="mb-10px flex items-center justify-between">
      <span class="text-14px">共 {{ mine.length }} 条我指导的获奖记录</span>
      <el-button :loading="loading" @click="getList">
        <Icon icon="ep:refresh" class="mr-5px" />刷新
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="mine"
      row-key="id"
      border
      :empty-text="emptyHint"
    >
      <el-table-column label="编号" prop="id" width="90" align="center" />
      <el-table-column label="竞赛名称" prop="name" min-width="240" show-overflow-tooltip />
      <el-table-column label="获奖等级" prop="competition_level" width="120" align="center">
        <template #default="scope">{{ scope.row.competition_level || '-' }}</template>
      </el-table-column>
      <el-table-column label="奖项" prop="award_level" width="110" align="center">
        <template #default="scope">{{ scope.row.award_level || '-' }}</template>
      </el-table-column>
      <el-table-column label="获奖人" prop="winner_name" min-width="140" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.winner_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="指导教师" prop="supervisor_name" min-width="150" show-overflow-tooltip />
      <el-table-column label="年份" prop="year" width="90" align="center">
        <template #default="scope">{{ scope.row.year ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="异常" width="90" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.is_abnormal ? 'danger' : 'success'" size="small">
            {{ scope.row.is_abnormal ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </ContentWrap>
</template>

<script setup lang="ts">
import { getVaultPage } from '@/api/business/achievement'
import { useUserStore } from '@/store/modules/user'

defineOptions({ name: 'TeacherAwards' })

const userStore = useUserStore()
const myName = computed(() => userStore.getUser?.nickname || '')

const loading = ref(false)
/** 后端返回的是全租户获奖记录,下面按指导教师在前端筛 */
const allRows = ref<any[]>([])

const queryParams = reactive({
  keyword: undefined
})

const queryFormRef = ref()

/** supervisor_name 可能是「王五」「王五,赵六」「王五、赵六」等多种写法 */
const isSupervisedByMe = (supervisorName: string | null | undefined) => {
  if (!supervisorName || !myName.value) {
    return false
  }
  return supervisorName
    .split(/[,，;；、\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .includes(myName.value.trim())
}

const mine = computed(() => {
  const kw = (queryParams.keyword || '').trim()
  return allRows.value.filter(
    (r) => isSupervisedByMe(r.supervisor_name) && (!kw || (r.name || '').includes(kw))
  )
})

const emptyHint = computed(() => {
  if (!myName.value) {
    return '取不到当前用户姓名'
  }
  if (allRows.value.length === 0) {
    return '还没有获奖记录入库'
  }
  return '没有指导教师含本人姓名的获奖记录'
})

const getList = async () => {
  loading.value = true
  try {
    // 一次拉 100 条(vault 端点 pageSize 后端夹在 1..100),前端再筛
    const res = await getVaultPage('award', { pageNo: 1, pageSize: 100, keyword: undefined })
    allRows.value = res.list || []
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  // 纯前端过滤,不需要重新请求
}

const resetQuery = () => {
  queryFormRef.value?.resetFields()
}

onMounted(getList)
</script>
