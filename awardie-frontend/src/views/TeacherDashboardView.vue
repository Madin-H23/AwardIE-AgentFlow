<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiJson } from '../composables/useCsrf'

// Goal D 对照 v1 teacher/dashboard_ref.html(148 行):信息卡(橙头像+部门/实验室/工号+技能 chips
// +获得成果/技术标签内嵌计数+右侧操作钮)+成果展示卡(最近成果列表,绿图标+黄标)。

interface Summary {
  name: string
  department: string
  teacherId: string
  laboratories: string[]
  skills: string[]
  skillsCount: number
  awardCount: number
  recentAwards: Array<{ competition: string | null; awardLevel: string | null; year: string | null; date: string | null }>
}
const summary = ref<Summary | null>(null)
const loading = ref(true)

onMounted(async () => {
  const body = await apiJson('GET', '/api/v2/teacher/portal/summary')
  if (body.code === 0) summary.value = body.data
  loading.value = false
})
</script>

<template>
  <div v-loading="loading">
    <!-- ① 个人信息卡 -->
    <div class="card profile-card">
      <div class="avatar">{{ (summary?.name ?? '教').slice(0, 1) }}</div>
      <div class="profile-info">
        <div class="name-row">
          <h3 class="name">{{ summary?.name ?? '教师' }}</h3>
          <span class="muted-xs">公开主页</span>
        </div>
        <div class="meta-row">
          <span v-if="summary?.department">{{ summary.department }}</span>
          <span
            v-for="lab in summary?.laboratories ?? []"
            :key="lab"
            class="lab-tag"
          >🏛 {{ lab }}</span>
          <span v-if="summary?.teacherId">工号:{{ summary.teacherId }}</span>
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
        </div>
        <div class="mini-stats">
          <div class="mini">
            <div class="mini-num green">
              {{ summary?.awardCount ?? 0 }}
            </div>
            <div class="mini-label">
              获得成果
            </div>
          </div>
          <div class="mini">
            <div class="mini-num purple">
              {{ summary?.skillsCount ?? 0 }}
            </div>
            <div class="mini-label">
              技术标签
            </div>
          </div>
        </div>
      </div>
      <div class="actions">
        <router-link
          to="/profile"
          class="ghost-btn"
        >个人设置</router-link>
      </div>
    </div>

    <!-- ② 成果展示卡 -->
    <div class="card">
      <div class="sec-head">
        <h3 class="sec-title">
          成果展示
        </h3>
        <router-link
          to="/teacher/achievements"
          class="more"
        >查看更多 →</router-link>
      </div>
      <div
        v-if="!summary?.recentAwards?.length"
        class="empty"
      >
        暂无成果记录
      </div>
      <div
        v-for="(a, i) in summary?.recentAwards ?? []"
        :key="i"
        class="award-item"
      >
        <div class="award-icon">✓</div>
        <div class="award-body">
          <div class="award-title">
            {{ a.competition || '-' }}
          </div>
          <div class="award-sub">
            {{ a.awardLevel || '-' }}<template v-if="a.year"> · {{ a.year }}</template>
          </div>
        </div>
        <span class="award-chip">竞赛获奖</span>
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
.profile-info { flex: 1; }
.name-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.name { font-size: 1.4rem; font-weight: 700; margin: 0; color: var(--ink); }
.muted-xs { font-size: 0.72rem; color: var(--ink-2); }
.meta-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  font-size: 0.85rem; color: var(--ink-2); margin-bottom: 8px;
}
.lab-tag {
  font-size: 0.78rem; font-weight: 500;
  background: color-mix(in srgb, #7222d1 8%, var(--panel));
  border: 1px solid color-mix(in srgb, #7222d1 25%, transparent);
  color: #7222d1; border-radius: 6px; padding: 2px 8px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.skill-tag {
  font-size: 0.74rem;
  background: color-mix(in srgb, #1677ff 10%, var(--panel));
  color: #1677ff; border-radius: 999px; padding: 2px 10px;
}
.mini-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 10px; }
.mini { text-align: center; }
.mini-num { font-size: 1.5rem; font-weight: 700; }
.mini-num.green { color: #16a34a; }
.mini-num.purple { color: #9333ea; }
.mini-label { font-size: 0.72rem; color: var(--ink-2); }
.actions { display: flex; flex-direction: column; gap: 10px; }
.ghost-btn {
  border: 1px solid var(--line); color: var(--ink-2);
  border-radius: 8px; padding: 7px 20px; font-size: 0.85rem;
  text-decoration: none; text-align: center; white-space: nowrap;
}
.ghost-btn:hover { color: var(--portal-accent); border-color: var(--portal-accent); }
.sec-head {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
}
.sec-title { font-size: 1.1rem; font-weight: 600; color: var(--ink); margin: 0; }
.more { color: var(--portal-accent); font-size: 0.85rem; text-decoration: none; }
.empty { text-align: center; color: var(--ink-2); font-size: 0.85rem; padding: 24px 0; }
.award-item {
  display: flex; align-items: flex-start; gap: 12px;
  border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px;
}
.award-icon {
  width: 44px; height: 44px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, #4ade80, #16a34a);
  color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700;
}
.award-body { flex: 1; }
.award-title { font-weight: 600; color: var(--ink); font-size: 0.92rem; }
.award-sub { font-size: 0.8rem; color: var(--ink-2); margin-top: 3px; }
.award-chip {
  background: var(--sev-warning-bg); color: var(--sev-warning);
  font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; align-self: flex-start;
}
</style>
