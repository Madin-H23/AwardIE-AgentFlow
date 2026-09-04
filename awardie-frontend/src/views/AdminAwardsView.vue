<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp, Search, Refresh } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'
import { useTablePage } from '../composables/useTablePage'
import { statusLabel, statusTagType, submitterTypeLabel, typeLabel } from '../composables/useBadge'
import PageHeader from '../components/PageHeader.vue'

const API = '/api/v2/admin/achievements'

interface Row {
  id: number
  achievementType: string
  submitterType: string
  submitterId: number
  status: string
}

// #37:筛选十维对照 v1 achievements(keyword/type/status/时间 + jsonb 六维:竞赛名称/年份/竞赛级别/获奖等级/获奖人/指导教师)
const tp = useTablePage<Row>({
  api: API,
  filters: {
    keyword: '', achievementType: '', status: '', dateFrom: '', dateTo: '',
    competitionName: '', year: '', competitionLevel: '', awardLevel: '', winnerName: '', supervisorName: '',
  },
})

const LEVELS = ['校赛', '区域赛', '省赛', '国赛', '国际赛']
const AWARDS = ['特等奖', '一等奖', '二等奖', '三等奖', '优秀奖']

const dateRange = ref<[string, string] | null>(null)

// UX-2 挂账小批(B5):十维筛选默认只露审核域三维,七维 jsonb/时间维折叠
const advanced = ref(false)

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
      <!-- UX-1 批3:标题与侧边栏"待审管理"对齐(治理导航/页内标题错位) -->
      <PageHeader
        title="待审管理"
        subtitle="待审记录跟踪与 admin 复核;批准入库 / 驳回打回(BR-5)"
      />
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
              :label="typeLabel(t)"
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
        <el-form-item>
          <el-button
            link
            type="primary"
            data-testid="filter-advanced-toggle"
            @click="advanced = !advanced"
          >
            {{ advanced ? '收起筛选' : '展开更多筛选' }}
            <el-icon><ArrowDown v-if="!advanced" /><ArrowUp v-else /></el-icon>
          </el-button>
        </el-form-item>
        <template v-if="advanced">
          <el-form-item label="竞赛名称">
            <el-input
              v-model="tp.filters.competitionName"
              placeholder="竞赛名称"
              style="width: 180px"
              clearable
              @keyup.enter="tp.search()"
              @clear="tp.search()"
            />
          </el-form-item>
          <el-form-item label="年份">
            <el-input
              v-model="tp.filters.year"
              placeholder="如 2026"
              style="width: 100px"
              clearable
              @keyup.enter="tp.search()"
              @clear="tp.search()"
            />
          </el-form-item>
          <el-form-item label="竞赛级别">
            <el-select
              v-model="tp.filters.competitionLevel"
              placeholder="全部"
              clearable
              style="width: 120px"
              @change="tp.search()"
            >
              <el-option
                v-for="lv in LEVELS"
                :key="lv"
                :label="lv"
                :value="lv"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="获奖等级">
            <el-select
              v-model="tp.filters.awardLevel"
              placeholder="全部"
              clearable
              style="width: 120px"
              @change="tp.search()"
            >
              <el-option
                v-for="lv in AWARDS"
                :key="lv"
                :label="lv"
                :value="lv"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="获奖人">
            <el-input
              v-model="tp.filters.winnerName"
              placeholder="获奖人"
              style="width: 120px"
              clearable
              @keyup.enter="tp.search()"
              @clear="tp.search()"
            />
          </el-form-item>
          <el-form-item label="指导教师">
            <el-input
              v-model="tp.filters.supervisorName"
              placeholder="指导教师"
              style="width: 120px"
              clearable
              @keyup.enter="tp.search()"
              @clear="tp.search()"
            />
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
        </template>
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
        >
          <template #default="scope">
            <span class="num">{{ scope.row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="类型"
          width="90"
        >
          <template #default="scope">
            <el-tag
              size="small"
              type="info"
              effect="plain"
            >
              {{ typeLabel(scope.row.achievementType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="提交者类型"
          width="110"
        >
          <template #default="scope">
            {{ submitterTypeLabel(scope.row.submitterType) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="submitterId"
          label="提交者ID"
          width="100"
        >
          <template #default="scope">
            <span class="num">{{ scope.row.submitterId }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="提交者姓名"
          width="110"
        >
          <template #default="scope">
            {{ scope.row.submitterName || '-' }}
          </template>
        </el-table-column>
        <el-table-column
          label="状态"
          width="100"
        >
          <template #default="scope">
            <el-tag
              size="small"
              :type="statusTagType(scope.row.status)"
            >
              {{ statusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
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
            <router-link
              :to="`/admin/review/${scope.row.id}`"
              data-testid="award-view"
            >
              <el-button size="small" text type="primary">
                查看
              </el-button>
            </router-link>
            <!-- UX-1 批3:Fix-V 模式推广——仅待审行可操作,已审行显示状态 tag(disabled 按钮诱导点击) -->
            <template v-if="scope.row.status === 'pending'">
              <el-button
                size="small"
                type="success"
                @click="review(scope.row.id, 'approve')"
              >
                通过
              </el-button>
              <el-button
                size="small"
                type="danger"
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
            <el-tag
              v-else
              size="small"
              :type="statusTagType(scope.row.status)"
            >
              {{ statusLabel(scope.row.status) }}
            </el-tag>
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
.admin-page { }
h2 { margin-top: 0; color: var(--ink); }
.filter-form { margin-bottom: 4px; }
</style>
