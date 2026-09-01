<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #29/#38 对照 v1 admin/students/list.html:页头+添加/搜索 c-panel/表格(学号/姓名/专业/年级/电话/激活)/分页
// +编辑/删除(v1 同款操作列)。

interface Row {
  id: number
  login_code: string
  name: string
  major: string | null
  grade: string | null
  phone: string | null
  user_activated: boolean
}
const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const search = ref('')
const loading = ref(false)

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  loginCode: '', name: '', major: '', grade: '', phone: '', skills: '',
})

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams({ page: String(page.value), size: String(size.value) })
    if (search.value) qs.set('search', search.value)
    const body = await apiJson('GET', `/api/v2/admin/students?${qs}`)
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

function openCreate() {
  editingId.value = null
  Object.assign(form, { loginCode: '', name: '', major: '', grade: '', phone: '', skills: '' })
  dialogVisible.value = true
}

function openEdit(row: Row) {
  editingId.value = row.id
  Object.assign(form, {
    loginCode: row.login_code, name: row.name, major: row.major ?? '',
    grade: row.grade ?? '', phone: row.phone ?? '', skills: '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('姓名必填')
    return
  }
  const body = editingId.value === null
    ? await apiJson('POST', '/api/v2/admin/users/student', { ...form })
    : await apiJson('PUT', `/api/v2/admin/users/student/${editingId.value}`, { ...form })
  if (body.code === 0) {
    ElMessage.success(body.message ?? '已保存')
    dialogVisible.value = false
    await load()
  } else {
    ElMessage.error(body.message)
  }
}

async function remove(row: Row) {
  const ok = await ElMessageBox.confirm(
    `确定删除学生 ${row.name}(${row.login_code})吗?存在关联成果时将拒绝。`, '删除确认', { type: 'warning' },
  ).catch(() => false)
  if (!ok) return
  const body = await apiJson('DELETE', `/api/v2/admin/users/student/${row.id}`)
  if (body.code === 0) {
    ElMessage.success('已删除')
    await load()
  } else {
    ElMessage.error(body.message)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <h1>学生管理</h1>
      <el-button
        type="primary"
        data-testid="student-create"
        @click="openCreate"
      >
        添加学生
      </el-button>
    </div>

    <div class="c-panel pad search-panel">
      <el-input
        v-model="search"
        placeholder="输入姓名或学号进行搜索"
        style="width: 280px"
        clearable
        data-testid="student-search"
        @keyup.enter="doSearch"
        @clear="doSearch"
      />
      <el-select
        v-model="size"
        style="width: 100px"
        @change="doSearch"
      >
        <el-option
          v-for="n in [20, 50, 100]"
          :key="n"
          :label="n + ' 条/页'"
          :value="n"
        />
      </el-select>
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
          label="学号"
          width="130"
        />
        <el-table-column
          prop="name"
          label="姓名"
          width="110"
        />
        <el-table-column label="专业">
          <template #default="scope">
            {{ scope.row.major || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="年级">
          <template #default="scope">
            {{ scope.row.grade || '-' }}
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
        <el-table-column
          label="操作"
          width="130"
        >
          <template #default="scope">
            <el-button
              size="small"
              text
              type="primary"
              @click="openEdit(scope.row)"
            >
              编辑
            </el-button>
            <el-button
              size="small"
              text
              type="danger"
              @click="remove(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        style="margin-top: 12px; justify-content: center"
        @current-change="(p: number) => { page = p; load() }"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '添加学生' : '编辑学生'"
      width="460px"
    >
      <el-form label-width="90px">
        <el-form-item label="学号">
          <el-input
            v-model="form.loginCode"
            :disabled="editingId !== null"
            placeholder="登录账号"
          />
        </el-form-item>
        <el-form-item
          label="姓名"
          required
        >
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="专业">
          <el-input v-model="form.major" />
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="form.grade" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item
          v-if="editingId === null"
          label="初始口令"
        >
          <el-input
            model-value="P@ss301(首登须修改)"
            disabled
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          data-testid="student-save"
          @click="save"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
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
