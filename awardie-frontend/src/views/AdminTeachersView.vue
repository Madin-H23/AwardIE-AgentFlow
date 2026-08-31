<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #29 对照 v1 admin/teachers/list.html:页头/搜索 c-panel(姓名或工号)/表格(工号/姓名/部门/职称/电话/激活)/分页。编辑挂后续票。
const rows = ref<Array<Record<string, unknown>>>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const search = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams({ page: String(page.value), size: String(size.value) })
    if (search.value) qs.set('search', search.value)
    const body = await apiJson('GET', `/api/v2/admin/teachers?${qs}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

function doSearch() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <h1>教师管理</h1>
      <el-tooltip content="教师新增/编辑按批次迁移中">
        <span><el-button
          type="primary"
          disabled
        >添加教师</el-button></span>
      </el-tooltip>
    </div>

    <div class="c-panel pad search-panel">
      <el-input
        v-model="search"
        placeholder="输入姓名或工号进行搜索"
        style="width: 280px"
        clearable
        data-testid="teacher-search"
        @keyup.enter="doSearch"
        @clear="doSearch"
      />
      <el-button
        type="primary"
        :icon="Search"
        @click="doSearch"
      >
        搜索
      </el-button>
    </div>

    <div class="c-panel pad">
      <div class="muted-line">
        共找到 {{ total }} 条记录
      </div>
      <el-table
        v-loading="loading"
        :data="rows"
        size="default"
      >
        <el-table-column
          prop="login_code"
          label="工号"
          width="130"
        />
        <el-table-column
          prop="name"
          label="姓名"
          width="110"
        />
        <el-table-column label="部门">
          <template #default="scope">
            {{ scope.row.department || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="职称">
          <template #default="scope">
            {{ scope.row.title || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="电话">
          <template #default="scope">
            {{ scope.row.phone || '-' }}
          </template>
        </el-table-column>
        <el-table-column
          label="激活状态"
          width="100"
        >
          <template #default="scope">
            <el-tag
              :type="scope.row.user_activated ? 'success' : 'info'"
              size="small"
            >
              {{ scope.row.user_activated ? '已激活' : '未激活' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        style="margin-top: 12px"
        @current-change="(p: number) => { page = p; load() }"
      />
    </div>
  </div>
</template>

<style scoped>
.search-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.muted-line {
  font-size: 0.8rem;
  color: var(--ink-2);
  margin-bottom: 10px;
}
</style>
