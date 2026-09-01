<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { OfficeBuilding } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #29/#38 对照 v1 laboratories/list:卡片网格+创建/编辑/删除(v1 laboratory_edit 同款字段:名称+简介)。
interface Lab {
  id: number
  name: string
  description: string | null
  created_at: string
}
const rows = ref<Lab[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(12)
const loading = ref(false)

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ name: '', description: '' })

async function load() {
  loading.value = true
  try {
    const body = await apiJson('GET', `/api/v2/admin/laboratories?page=${page.value}&size=${size.value}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', description: '' })
  dialogVisible.value = true
}

function openEdit(lab: Lab) {
  editingId.value = lab.id
  Object.assign(form, { name: lab.name, description: lab.description ?? '' })
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('实验室名称必填')
    return
  }
  const body = editingId.value === null
    ? await apiJson('POST', '/api/v2/admin/laboratories', { ...form })
    : await apiJson('PUT', `/api/v2/admin/laboratories/${editingId.value}`, { ...form })
  if (body.code === 0) {
    ElMessage.success(body.message ?? '已保存')
    dialogVisible.value = false
    await load()
  } else {
    ElMessage.error(body.message)
  }
}

async function remove(lab: Lab) {
  const ok = await ElMessageBox.confirm(
    `确定删除实验室 ${lab.name} 吗?存在关联数据时将拒绝。`, '删除确认', { type: 'warning' },
  ).catch(() => false)
  if (!ok) return
  const body = await apiJson('DELETE', `/api/v2/admin/laboratories/${lab.id}`)
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
      <h1>实验室管理</h1>
      <el-button
        type="primary"
        data-testid="lab-create"
        @click="openCreate"
      >
        创建实验室
      </el-button>
    </div>

    <div
      v-loading="loading"
      class="c-panel pad"
    >
      <div
        v-if="!rows.length && !loading"
        class="empty-state"
      >
        暂无实验室
      </div>
      <el-row :gutter="14">
        <el-col
          v-for="lab in rows"
          :key="lab.id"
          :span="8"
          style="margin-bottom: 14px"
        >
          <div class="lab-card">
            <div class="lab-cover">
              <el-icon :size="34"><OfficeBuilding /></el-icon>
            </div>
            <div class="lab-body">
              <div class="lab-name">
                {{ lab.name }}
              </div>
              <div class="lab-desc">
                {{ lab.description || '暂无简介' }}
              </div>
              <div class="lab-foot">
                <span class="lab-time">建于 {{ String(lab.created_at).slice(0, 10) }}</span>
                <span>
                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click="openEdit(lab)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click="remove(lab)"
                  >
                    删除
                  </el-button>
                </span>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
      <el-pagination
        v-if="total > size"
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        style="margin-top: 8px"
        @current-change="(p: number) => { page = p; load() }"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '创建实验室' : '编辑实验室'"
      width="460px"
    >
      <el-form label-width="80px">
        <el-form-item
          label="名称"
          required
        >
          <el-input
            v-model="form.name"
            data-testid="lab-name"
          />
        </el-form-item>
        <el-form-item label="简介">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          data-testid="lab-save"
          @click="save"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lab-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.15s;
}
.lab-card:hover { border-color: var(--brand); }
.lab-cover {
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--brand) 8%, var(--panel));
  color: var(--brand);
}
.lab-body { padding: 12px 14px; }
.lab-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--ink);
}
.lab-desc {
  font-size: 0.8rem;
  color: var(--ink-2);
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.4em;
}
.lab-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.lab-time {
  font-size: 0.72rem;
  color: var(--ink-2);
}
.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--ink-2);
  font-size: 0.88rem;
}
</style>
