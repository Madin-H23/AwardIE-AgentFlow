<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiJson } from '../composables/useCsrf'
import { statusLabel, statusTagType } from '../composables/useBadge'

// #35 对照 v1 student/achievements_ref.html(852 行):成果展示——四类成果 + 筛选 + 详情。

interface AwardRow {
  competition: string | null
  level: string | null
  awardLevel: string | null
  year: string | null
}
interface InnovRow {
  projectNo: string
  projectName: string
  projectType: string
  leader: string
  supervisors: string
  status: string
}
interface Achievements {
  awards: AwardRow[]
  innovations: InnovRow[]
  patents: Array<{ id: number; patentName: string; patentType: string }>
  software: Array<{ id: number; softwareName: string; registrationNumber: string }>
}

const ach = ref<Achievements | null>(null)
const loading = ref(true)
const keyword = ref('')
const activeTab = ref('awards')
const detail = ref<Record<string, string> | null>(null)
const detailVisible = ref(false)

const LEVEL_CLASS: Record<string, string> = { A类: 'lv-a', B类: 'lv-b', C类: 'lv-c' }

const years = computed(() => {
  const set = new Set<string>()
  ach.value?.awards.forEach((a) => a.year && set.add(String(a.year)))
  return [...set].sort().reverse()
})
const yearFilter = ref('')

const filteredAwards = computed(() =>
  (ach.value?.awards ?? []).filter(
    (a) =>
      (!yearFilter.value || String(a.year) === yearFilter.value) &&
      (!keyword.value || (a.competition ?? '').includes(keyword.value)),
  ),
)

function openDetail(row: Record<string, unknown>) {
  detail.value = Object.fromEntries(
    Object.entries(row).map(([k, v]) => [k, v == null || v === '' ? '-' : String(v)]),
  )
  detailVisible.value = true
}

onMounted(async () => {
  const body = await apiJson('GET', '/api/v2/student/portal/achievements')
  if (body.code === 0) ach.value = body.data
  loading.value = false
})
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>成果展示</h1>
      <div class="filters">
        <el-input
          v-model="keyword"
          placeholder="竞赛名称筛选"
          style="width: 200px"
          clearable
        />
        <el-select
          v-model="yearFilter"
          placeholder="全部年份"
          clearable
          style="width: 120px"
        >
          <el-option
            v-for="y in years"
            :key="y"
            :label="y"
            :value="y"
          />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane
        :label="`获奖(${ach?.awards.length ?? 0})`"
        name="awards"
      >
        <el-table
          :data="filteredAwards"
          size="small"
          @row-click="openDetail"
        >
          <el-table-column
            prop="competition"
            label="竞赛名称"
            min-width="240"
          />
          <el-table-column
            label="竞赛级别"
            width="110"
          >
            <template #default="scope">
              <span
                v-if="scope.row.level"
                class="lv-tag"
                :class="LEVEL_CLASS[scope.row.level] ?? 'lv-other'"
              >{{ scope.row.level }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="awardLevel"
            label="获奖等级"
            width="110"
          />
          <el-table-column
            prop="year"
            label="年份"
            width="80"
          />
        </el-table>
      </el-tab-pane>
      <el-tab-pane
        :label="`大创(${ach?.innovations.length ?? 0})`"
        name="innovations"
      >
        <el-table
          :data="ach?.innovations ?? []"
          size="small"
          @row-click="openDetail"
        >
          <el-table-column
            prop="projectNo"
            label="项目编号"
            width="140"
          />
          <el-table-column
            prop="projectName"
            label="项目名称"
            min-width="220"
          />
          <el-table-column
            prop="projectType"
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
            label="状态"
            width="90"
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
        </el-table>
      </el-tab-pane>
      <el-tab-pane
        :label="`专利(${ach?.patents.length ?? 0})`"
        name="patents"
      >
        <el-table
          :data="ach?.patents ?? []"
          size="small"
          @row-click="openDetail"
        >
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="patentName"
            label="专利名称"
            min-width="240"
          />
          <el-table-column
            prop="patentType"
            label="类型"
            width="120"
          />
        </el-table>
      </el-tab-pane>
      <el-tab-pane
        :label="`软著(${ach?.software.length ?? 0})`"
        name="software"
      >
        <el-table
          :data="ach?.software ?? []"
          size="small"
          @row-click="openDetail"
        >
          <el-table-column
            prop="id"
            label="ID"
            width="70"
            class-name="num"
          />
          <el-table-column
            prop="softwareName"
            label="软件名称"
            min-width="240"
          />
          <el-table-column
            prop="registrationNumber"
            label="登记号"
            width="160"
          />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="detailVisible"
      title="成果详情"
      width="420px"
    >
      <div
        v-if="detail"
        class="detail"
      >
        <div
          v-for="(v, k) in detail"
          :key="k"
          class="d-row"
        >
          <span class="d-k">{{ k }}</span>
          <span class="d-v">{{ v }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.page-head h1 { font-size: 1.35rem; font-weight: 700; color: var(--ink); margin: 0; }
.filters { display: flex; gap: 10px; }
.lv-tag {
  font-size: 0.72rem; padding: 2px 8px; border-radius: 999px;
  background: color-mix(in srgb, var(--ink) 6%, transparent); color: var(--ink-2);
}
.lv-tag.lv-a { background: var(--sev-error-bg); color: var(--sev-error); }
.lv-tag.lv-b { background: var(--sev-warning-bg); color: var(--sev-warning); }
.lv-tag.lv-c { background: var(--sev-warning-bg); color: var(--sev-warning); }
.detail { max-height: 420px; overflow-y: auto; }
.d-row {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 7px 0; border-bottom: 1px dashed var(--line); font-size: 0.85rem;
}
.d-k { color: var(--ink-2); flex-shrink: 0; }
.d-v { color: var(--ink); text-align: right; }
</style>
