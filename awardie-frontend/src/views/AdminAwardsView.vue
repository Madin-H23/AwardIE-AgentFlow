<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'
import { useTablePage } from '../composables/useTablePage'

const API = '/api/v2/admin/achievements'

interface Row {
  id: number
  achievementType: string
  submitterType: string
  submitterId: number
  status: string
}

// #27:useTablePage 统一分页+筛选+loading;筛选四维吃满 #26 Specification(keyword/type/status/时间)
const tp = useTablePage<Row>({
  api: API,
  filters: { keyword: '', achievementType: '', status: '', dateFrom: '', dateTo: '' },
})

const dateRange = ref<[string, string] | null>(null)

function applyRange() {
  tp.filters.dateFrom = dateRange.value?.[0] ?? ''
  tp.filters.dateTo = dateRange.value?.[1] ?? ''
  tp.search()
}

function resetRange() {
  dateRange.value = null
  tp.reset()
}

const rejectId = ref<number | null>(null)
const rejectComment = ref('')

async function review(id: number, action: 'approve' | 'reject') {
  const body = await apiJson('POST', `${API}/${id}/review`, {
    action,
    comment: action === 'reject' ? rejectComment.value : 'admin 复核通过',
  })
  if (body.code === 0) {
    ElMessage.success(`#${id} 已${action === 'approve' ? '批准入库' : '驳回'}`)
    rejectId.value = null
    rejectComment.value = ''
    await tp.load()
  } else {
    ElMessage.error(body.message)
  }
}

onMounted(tp.load)
</script>

<template>
  <div class="admin-page">
    <el-card>
      <h2>成果管理</h2>
      <el-form
        inline
        class="filter-form"
        @submit.prevent
      >
        <el-form-item label="关键词">
          <el-input
            v-model="tp.filters.keyword"
            placeholder="名称/竞赛/获奖人(jsonb 模糊)"
            style="width: 220px"
            clearable
            data-testid="filter-keyword"
            @keyup.enter="tp.search()"
            @clear="tp.search()"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="tp.filters.achievementType"
            placeholder="全部"
            style="width: 120px"
            clearable
            @change="tp.search()"
          >
            <el-option
              v-for="t in ['award', 'patent', 'software', 'innovation', 'other']"
              :key="t"
              :label="t"
              :value="t"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="tp.filters.status"
            placeholder="全部"
            style="width: 120px"
            clearable
            @change="tp.search()"
          >
            <el-option
              label="待审"
              value="pending"
            />
            <el-option
              label="已归档"
              value="archived"
            />
            <el-option
              label="已驳回"
              value="rejected"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="提交于">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :icon="Search"
            data-testid="filter-search"
            @click="applyRange"
          >
            查询
          </el-button>
          <el-button
            :icon="Refresh"
            @click="resetRange"
          >
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <el-table
        v-loading="tp.loading.value"
        :data="tp.rows.value"
        size="small"
      >
        <el-table-column
          prop="id"
          label="#"
          width="80"
        />
        <el-table-column
          prop="achievementType"
          label="类型"
          width="100"
        />
        <el-table-column
          prop="submitterType"
          label="提交者类型"
          width="110"
        />
        <el-table-column
          prop="submitterId"
          label="提交者ID"
          width="100"
        />
        <el-table-column
          prop="status"
          label="状态"
          width="110"
        />
        <el-table-column
          label="文件"
          width="90"
        >
          <template #default="scope">
            <el-link
              :href="`/api/v2/files/${scope.row.id}/download`"
              target="_blank"
            >
              下载
            </el-link>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          min-width="240"
        >
          <template #default="scope">
            <el-button
              size="small"
              type="success"
              :disabled="scope.row.status !== 'pending'"
              @click="review(scope.row.id, 'approve')"
            >
              通过
            </el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="scope.row.status !== 'pending'"
              @click="rejectId = scope.row.id"
            >
              驳回
            </el-button>
            <el-input
              v-if="rejectId === scope.row.id"
              v-model="rejectComment"
              size="small"
              style="width: 180px"
              placeholder="驳回原因(BR-5 必填)"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        layout="prev, pager, next"
        :total="tp.total.value"
        :page-size="tp.size.value"
        :current-page="tp.page.value"
        style="margin-top: 12px"
        @current-change="tp.go"
      />
    </el-card>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1200px; }
h2 { margin-top: 0; color: var(--ink); }
.filter-form { margin-bottom: 4px; }
</style>
