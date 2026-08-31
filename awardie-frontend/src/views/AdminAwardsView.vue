<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

const API = '/api/v2/admin/achievements'
const rows = ref<Array<Record<string, unknown>>>([])
const total = ref(0)
const page = ref(0)
const statusFilter = ref('')
const rejectId = ref<number | null>(null)
const rejectComment = ref('')

async function load() {
  const q = new URLSearchParams({ page: String(page.value), size: '20' })
  if (statusFilter.value) q.set('status', statusFilter.value)
  const body = await apiJson('GET', `${API}?${q}`)
  if (body.code === 0) {
    rows.value = body.data.content
    total.value = body.data.totalElements
  }
}
onMounted(load)

async function review(id: number, action: 'approve' | 'reject') {
  const body = await apiJson('POST', `${API}/${id}/review`, {
    action,
    comment: action === 'reject' ? rejectComment.value : 'admin 复核通过',
  })
  if (body.code === 0) {
    ElMessage.success(`#${id} 已${action === 'approve' ? '批准入库' : '驳回'}`)
    rejectId.value = null
    rejectComment.value = ''
    await load()
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div class="admin-page">
    <el-card>
      <h2>成果管理(award)</h2>
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        style="width: 160px"
        @change="load"
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
      <el-table
        :data="rows"
        size="small"
        style="margin-top: 12px"
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
        :total="total"
        :page-size="20"
        style="margin-top: 12px"
        @current-change="(p: number) => { page = p - 1; load() }"
      />
    </el-card>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1100px; margin: 24px auto; }
h2 { margin-top: 0; color: var(--ink); }
</style>
