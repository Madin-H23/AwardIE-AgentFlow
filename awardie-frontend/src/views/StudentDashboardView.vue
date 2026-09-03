<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'
import { statusLabel, statusTagType } from '../composables/useBadge'

// #35 对照 v1 student/dashboard_ref.html:个人信息卡(头像+公开主页开关+年级专业学号+实验室/技能标签)
// +统计卡三列(获奖/大创/技术标签)+成果展示区(获奖/大创/专利/软著四表,空态引导提交)。

interface Summary {
  name: string
  grade: string
  major: string
  studentId: string
  publicProfile: boolean
  laboratories: string[]
  skills: string[]
  skillsCount: number
  awardCount: number
  innovationCount: number
}
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

const summary = ref<Summary | null>(null)
const ach = ref<Achievements | null>(null)
const loading = ref(true)

const LEVEL_CLASS: Record<string, string> = {
  A类: 'lv-a', B类: 'lv-b', C类: 'lv-c',
}

onMounted(async () => {
  const [s, a] = await Promise.all([
    apiJson('GET', '/api/v2/student/portal/summary'),
    apiJson('GET', '/api/v2/student/portal/achievements'),
  ])
  if (s.code === 0) summary.value = s.data
  if (a.code === 0) ach.value = a.data
  loading.value = false
})

/** #37:公开主页开关(v1 togglePublicProfile 的 TODO 落地)——GET /profile 全量合并后 PUT。 */
async function togglePublic(v: boolean | string | number) {
  const p = await apiJson('GET', '/api/v2/profile')
  if (p.code !== 0) {
    ElMessage.error('读取资料失败')
    return
  }
  const save = await apiJson('PUT', '/api/v2/profile', { ...p.data, profileIsPublic: Boolean(v) })
  if (save.code === 0) ElMessage.success(Boolean(v) ? '已设为公开' : '已设为私密')
  else ElMessage.error(save.message)
}

/** #37:导出全部(对照 v1 student.export_all)——四类成果汇总 CSV。 */
function exportAll() {
  const a = document.createElement('a')
  a.href = '/api/v2/student/portal/export.csv'
  a.download = 'my-achievements.csv'
  a.click()
}
</script>

<template>
  <div v-loading="loading">
    <!-- ① 个人信息卡 -->
    <div class="card profile-card">
      <div class="avatar">
        {{ (summary?.name ?? '学').slice(0, 1) }}
      </div>
      <div class="profile-info">
        <div class="name-row">
          <h3 class="name">
            {{ summary?.name ?? '学生' }}
          </h3>
          <el-switch
            :model-value="summary?.publicProfile ?? false"
            size="small"
            @change="(v: boolean | string | number) => togglePublic(v)"
          />
          <span class="muted-xs">公开主页</span>
        </div>
        <div class="meta-row">
          <span v-if="summary?.grade">{{ summary.grade }}</span>
          <span v-if="summary?.major">{{ summary.major }}</span>
          <span v-if="summary?.studentId">学号:{{ summary.studentId }}</span>
        </div>
        <div
          v-if="summary?.laboratories?.length"
          class="tag-row"
        >
          <span
            v-for="lab in summary.laboratories"
            :key="lab"
            class="lab-tag"
          >🏛 {{ lab }}</span>
        </div>
        <div
          v-if="summary?.skills?.length"
          class="tag-row"
        >
          <span
            v-for="sk in summary.skills.slice(0, 8)"
            :key="sk"
            class="skill-tag"
          >{{ sk }}</span>
          <span
            v-if="summary.skills.length > 8"
            class="skill-more"
          >+{{ summary.skills.length - 8 }}</span>
        </div>
      </div>
    </div>

    <!-- ② 统计卡 -->
    <div class="stat-grid">
      <div class="card stat-card">
        <div class="stat-num green">
          {{ summary?.awardCount ?? 0 }}
        </div>
        <div class="stat-label">
          获奖数量
        </div>
      </div>
      <div class="card stat-card">
        <div class="stat-num orange">
          {{ summary?.innovationCount ?? 0 }}
        </div>
        <div class="stat-label">
          大创数量
        </div>
      </div>
      <div class="card stat-card">
        <div class="stat-num blue">
          {{ summary?.skillsCount ?? 0 }}
        </div>
        <div class="stat-label">
          技术标签
        </div>
      </div>
    </div>

    <!-- ③ 成果展示 -->
    <div class="section-head">
      <h2 class="sec-title">
        我的成果
      </h2>
      <el-button
        type="primary"
        data-testid="export-all"
        @click="exportAll"
      >
        导出全部
      </el-button>
    </div>

    <div
      v-if="!loading && !ach?.awards.length && !ach?.innovations.length && !ach?.patents.length && !ach?.software.length"
      class="card empty"
    >
      <h3>暂无成果记录</h3>
      <p>开始提交您的第一份成果吧!</p>
      <router-link
        to="/submit"
        class="submit-btn"
      >
        + 提交成果
      </router-link>
    </div>

    <div
      v-else
      class="tables"
    >
      <div
        v-if="ach?.awards.length"
        class="card"
      >
        <h3 class="tbl-title">
          获奖记录({{ ach.awards.length }}项)
        </h3>
        <el-table
          :data="ach.awards"
          size="small"
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
            label="获奖等级"
            width="110"
          >
            <template #default="scope">
              {{ scope.row.awardLevel || '-' }}
            </template>
          </el-table-column>
          <el-table-column
            label="年份"
            width="80"
          >
            <template #default="scope">
              {{ scope.row.year || '-' }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div
        v-if="ach?.innovations.length"
        class="card"
      >
        <h3 class="tbl-title">
          大创项目({{ ach.innovations.length }}项)
        </h3>
        <el-table
          :data="ach.innovations"
          size="small"
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
      </div>

      <div
        v-if="ach?.patents.length"
        class="card"
      >
        <h3 class="tbl-title">
          专利({{ ach.patents.length }}项)
        </h3>
        <el-table
          :data="ach.patents"
          size="small"
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
            min-width="220"
          />
          <el-table-column
            prop="patentType"
            label="类型"
            width="110"
          />
        </el-table>
      </div>

      <div
        v-if="ach?.software.length"
        class="card"
      >
        <h3 class="tbl-title">
          软著({{ ach.software.length }}项)
        </h3>
        <el-table
          :data="ach.software"
          size="small"
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
            min-width="220"
          />
          <el-table-column
            prop="registrationNumber"
            label="登记号"
            width="160"
          />
        </el-table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 16px;
}
.profile-card { display: flex; gap: 16px; align-items: flex-start; }
.avatar {
  width: 64px; height: 64px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, #fb923c, #ea580c);
  color: #fff; font-size: 1.5rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.name-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.name { font-size: 1.4rem; font-weight: 700; margin: 0; color: var(--ink); }
.muted-xs { font-size: 0.72rem; color: var(--ink-2); }
.meta-row {
  display: flex; flex-wrap: wrap; gap: 10px;
  font-size: 0.85rem; color: var(--ink-2); margin-bottom: 8px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
.lab-tag {
  font-size: 0.78rem; font-weight: 500;
  background: color-mix(in srgb, #7222d1 8%, var(--panel));
  border: 1px solid color-mix(in srgb, #7222d1 25%, transparent);
  color: #7222d1; border-radius: 6px; padding: 2px 8px;
}
.skill-tag {
  font-size: 0.74rem;
  background: color-mix(in srgb, #1677ff 10%, var(--panel));
  color: #1677ff; border-radius: 999px; padding: 2px 10px;
}
.skill-more { font-size: 0.74rem; color: var(--ink-2); }

.stat-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 22px;
}
.stat-card { text-align: center; }
.stat-num { font-size: 1.7rem; font-weight: 700; }
.stat-num.green { color: #16a34a; }
.stat-num.orange { color: var(--portal-accent); }
.stat-num.blue { color: #2563eb; }
.stat-label { font-size: 0.82rem; color: var(--ink-2); margin-top: 4px; }

.section-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.sec-title { font-size: 1.35rem; font-weight: 700; color: var(--ink); margin: 0; }
.empty { text-align: center; padding: 48px 20px; }
.empty h3 { margin: 0 0 6px; color: var(--ink); }
.empty p { color: var(--ink-2); margin: 0 0 18px; font-size: 0.88rem; }
.submit-btn {
  display: inline-block;
  background: linear-gradient(90deg, #f97316, #ea580c);
  color: #fff; text-decoration: none;
  padding: 8px 22px; border-radius: 8px; font-size: 0.9rem;
}
.tbl-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.lv-tag {
  font-size: 0.72rem; padding: 2px 8px; border-radius: 999px;
  background: color-mix(in srgb, var(--ink) 6%, transparent); color: var(--ink-2);
}
.lv-tag.lv-a { background: var(--sev-error-bg); color: var(--sev-error); }
.lv-tag.lv-b { background: var(--sev-warning-bg); color: var(--sev-warning); }
.lv-tag.lv-c { background: var(--sev-warning-bg); color: var(--sev-warning); }
</style>
