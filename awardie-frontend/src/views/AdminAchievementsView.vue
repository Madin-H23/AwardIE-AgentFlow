<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// Fix-C 对照 v1 admin/achievements.html:五类成果 tabs(奖状/专利/软著/大创/其他)
// +keyword 筛选+异常徽标+实验室列+行编辑/删除。区别于待审池(/admin/awards)。

interface Row {
  id: number
  name: string
  [key: string]: unknown
}
const activeTab = ref('award')
const keyword = ref('')
const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(0)
const size = ref(20)
const loading = ref(false)

const TABS = [
  { key: 'award', label: '奖状管理' },
  { key: 'patent', label: '专利管理' },
  { key: 'software', label: '软著管理' },
  { key: 'innovation', label: '大创管理' },
  { key: 'other', label: '其他文件管理' },
]

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams({ page: String(page.value), size: String(size.value) })
    if (keyword.value) qs.set('keyword', keyword.value)
    const body = await apiJson('GET', `/api/v2/admin/vault/${activeTab.value}?${qs}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

function doSearch() {
  page.value = 0
  load()
}

function switchTab() {
  page.value = 0
  load()
}

const editVisible = ref(false)
const editForm = reactive({
  id: 0, competitionName: '', competitionLevel: '', awardLevel: '',
  winnerName: '', supervisorName: '', laboratory: '',
})

// Fix-T:四类成果 tab 的详情编辑页跳转
function detailEditLink(tab: string, rid: number): string {
  if (tab === 'award') return `/admin/awards/${rid}/edit`
  if (tab === 'patent') return `/admin/patents/${rid}/edit`
  if (tab === 'software') return `/admin/software/${rid}/edit`
  return `/admin/innovation/${rid}/edit`
}

function openEdit(row: Row) {
  Object.assign(editForm, {
    id: row.id,
    competitionName: String(row.name ?? ''),
    competitionLevel: String(row.level ?? ''),
    awardLevel: String(row.award_level ?? ''),
    winnerName: String(row.winner_name ?? ''),
    supervisorName: String(row.supervisor_name ?? ''),
    laboratory: String(row.laboratory ?? ''),
  })
  editVisible.value = true
}

async function saveEdit() {
  const body = await apiJson('PUT', `/api/v2/admin/vault/awards/${editForm.id}`, {
    awardLevel: editForm.awardLevel || null,
    winnerName: editForm.winnerName || null,
    supervisorName: editForm.supervisorName || null,
    laboratoryId: null,
  })
  if (body.code === 0) {
    ElMessage.success('已更新')
    editVisible.value = false
    await load()
  } else {
    ElMessage.error(body.message)
  }
}

async function remove(row: Row) {
  const ok = await ElMessageBox.confirm(
    `确定删除${TABS.find((t) => t.key === activeTab.value)?.label ?? ''}记录 #${row.id}(${row.name})吗?存在关联数据时将拒绝。`,
    '删除确认', { type: 'warning' },
  ).catch(() => false)
  if (!ok) return
  const body = await apiJson('DELETE', `/api/v2/admin/vault/${activeTab.value}/${row.id}`)
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
      <h1>成果管理(成果库)</h1>
      <el-button
        text
        type="primary"
        @click="$router.push('/admin/awards')"
      >
        切换到待审管理 →
      </el-button>
    </div>

    <el-tabs
      v-model="activeTab"
      @tab-change="switchTab"
    >
      <el-tab-pane
        v-for="t in TABS"
        :key="t.key"
        :label="t.label"
        :name="t.key"
      />
    </el-tabs>

    <div class="c-panel pad filter-bar">
      <el-input
        v-model="keyword"
        :placeholder="activeTab === 'award' ? '竞赛名称筛选' : '名称筛选'"
        style="width: 240px"
        clearable
        @keyup.enter="doSearch"
        @clear="doSearch"
      />
      <el-button
        type="primary"
        :icon="Search"
        @click="doSearch"
      >
        筛选
      </el-button>
    </div>

    <div class="c-panel pad">
      <el-table
        v-loading="loading"
        :data="rows"
        size="small"
      >
        <template v-if="activeTab === 'award'">
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="name"
            label="竞赛名称"
            min-width="220"
          />
          <el-table-column
            label="竞赛级别"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.level || '-' }}
            </template>
          </el-table-column>
          <el-table-column
            label="获奖等级"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.award_level || '-' }}
            </template>
          </el-table-column>
          <el-table-column
            prop="winner_name"
            label="获奖人"
            width="100"
          />
          <el-table-column
            prop="supervisor_name"
            label="指导教师"
            width="110"
          />
          <el-table-column
            label="关联实验室"
            width="150"
          >
            <template #default="scope">
              {{ scope.row.laboratory || '-' }}
            </template>
          </el-table-column>
          <el-table-column
            prop="year"
            label="年份"
            width="80"
            class-name="num"
          />
          <el-table-column
            label="异常"
            width="80"
          >
            <template #default="scope">
              <el-tag
                v-if="scope.row.is_abnormal"
                type="danger"
                size="small"
              >
                异常
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="190"
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
              <router-link
                v-if="['award', 'patent', 'software', 'innovation'].includes(activeTab)"
                :to="detailEditLink(activeTab, scope.row.id)"
                data-testid="achievement-full-edit"
              >
                <el-button
                  size="small"
                  text
                  type="primary"
                >
                  详情编辑
                </el-button>
              </router-link>
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
        </template>

        <template v-else-if="activeTab === 'patent'">
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="name"
            label="专利名称"
            min-width="220"
          />
          <el-table-column
            prop="patent_type"
            label="类型"
            width="120"
          />
          <el-table-column
            prop="patentee"
            label="专利权人"
            min-width="140"
          />
          <el-table-column
            prop="inventor"
            label="发明人"
            min-width="120"
          />
          <el-table-column
            label="操作"
            width="90"
          >
            <template #default="scope">
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
        </template>

        <template v-else-if="activeTab === 'software'">
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="name"
            label="软件名称"
            min-width="220"
          />
          <el-table-column
            prop="software_version"
            label="版本"
            width="100"
          />
          <el-table-column
            prop="registration_number"
            label="登记号"
            width="160"
          />
          <el-table-column
            prop="copyright_owner"
            label="著作权人"
            min-width="140"
          />
          <el-table-column
            label="操作"
            width="90"
          >
            <template #default="scope">
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
        </template>

        <template v-else-if="activeTab === 'innovation'">
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="project_no"
            label="项目编号"
            width="140"
          />
          <el-table-column
            prop="name"
            label="项目名称"
            min-width="220"
          />
          <el-table-column
            prop="project_type"
            label="级别"
            width="90"
          />
          <el-table-column
            prop="leader"
            label="负责人"
            width="100"
          />
          <el-table-column
            prop="supervisors"
            label="指导教师"
            width="140"
          />
          <el-table-column
            prop="status"
            label="状态"
            width="90"
          />
          <el-table-column
            label="操作"
            width="90"
          >
            <template #default="scope">
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
        </template>

        <template v-else>
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="name"
            label="文件名"
            min-width="220"
          />
          <el-table-column
            prop="file_type"
            label="类型"
            width="100"
          />
          <el-table-column
            label="大小"
            width="110"
          >
            <template #default="scope">
              {{ scope.row.file_size ? (scope.row.file_size / 1024).toFixed(1) + ' KB' : '-' }}
            </template>
          </el-table-column>
          <el-table-column
            prop="description"
            label="描述"
            min-width="180"
          />
          <el-table-column
            label="操作"
            width="90"
          >
            <template #default="scope">
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
        </template>
      </el-table>
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page + 1"
        style="margin-top: 12px"
        @current-change="(p: number) => { page = p - 1; load() }"
      />
    </div>

    <el-dialog
      v-model="editVisible"
      title="编辑奖状记录"
      width="460px"
    >
      <el-form label-width="90px">
        <el-form-item label="竞赛名称">
          <el-input
            v-model="editForm.competitionName"
            disabled
          />
        </el-form-item>
        <el-form-item label="竞赛级别">
          <el-input v-model="editForm.competitionLevel" />
        </el-form-item>
        <el-form-item label="获奖等级">
          <el-input v-model="editForm.awardLevel" />
        </el-form-item>
        <el-form-item label="获奖人">
          <el-input v-model="editForm.winnerName" />
        </el-form-item>
        <el-form-item label="指导教师">
          <el-input v-model="editForm.supervisorName" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          data-testid="vault-save"
          @click="saveEdit"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
</style>
