<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { apiJson } from '../composables/useCsrf'

// #29 对照 v1 admin/logs/console_logs.html:三 tab(日志查看/分析看板/行动计划);
// 本轮实现 Tab1 双源(审核留痕 audit / 系统事件 system),看板与行动计划挂后续票(el-empty 占位)。
const activeTab = ref('viewer')
const source = ref<'audit' | 'system'>('audit')
const level = ref('')
const keyword = ref('')
const rows = ref<Array<Record<string, unknown>>>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const dateRange = ref<[string, string] | null>(null)

function reloadFromFirst() {
  page.value = 1
  load()
}

const ACTION_LABELS: Record<number, string> = {
  1: '提交', 6: '审核通过', 7: '驳回', 8: '物化入库',
}
const LEVEL_CLASS: Record<string, string> = {
  debug: 'lv-debug', info: 'lv-info', warning: 'lv-warning', error: 'lv-error', critical: 'lv-critical',
}

function fmtTime(v: unknown): string {
  return v ? String(v).slice(0, 19).replace('T', ' ') : '-'
}

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams({ source: source.value, page: String(page.value), size: String(size.value) })
    if (level.value) qs.set('level', level.value)
    if (keyword.value) qs.set('keyword', keyword.value)
    if (dateRange.value?.[0]) qs.set('dateFrom', dateRange.value[0])
    if (dateRange.value?.[1]) qs.set('dateTo', dateRange.value[1])
    const body = await apiJson('GET', `/api/v2/admin/logs?${qs}`)
    if (body.code === 0) {
      rows.value = body.data.content
      total.value = body.data.totalElements
    }
  } finally {
    loading.value = false
  }
}

function switchSource(s: 'audit' | 'system') {
  source.value = s
  page.value = 1
  load()
}

onMounted(load)

// #42 实时流(对照 v1 日志四源之"实时流"):SSE 增量追加 system_event_log,可暂停;应用日志(文件 tail)属 v1 Python 资产不迁移。
interface StreamLine {
  id: number
  level: string
  category: string
  message: string
  trace: string
  module: string
  time: string
}
const streamLines = ref<StreamLine[]>([])
const streamPaused = ref(false)
const streamRunning = ref(false)
const streamEl = ref<HTMLDivElement>()
let es: EventSource | null = null

function startStream() {
  if (es) return
  streamRunning.value = true
  es = new EventSource(`/api/v2/admin/logs/stream?afterId=0`, { withCredentials: true })
  es.addEventListener('anchor', () => { /* 锚点:仅初始化游标,不回放历史 */ })
  es.addEventListener('log', (e) => {
    if (streamPaused.value) return
    const line = JSON.parse((e as MessageEvent).data) as StreamLine
    streamLines.value.push(line)
    if (streamLines.value.length > 500) streamLines.value.splice(0, streamLines.value.length - 500)
    nextTick(() => streamEl.value?.scrollTo({ top: streamEl.value.scrollHeight }))
  })
  es.onerror = () => stopStream()
}

function stopStream() {
  es?.close()
  es = null
  streamRunning.value = false
}

function toggleStream() {
  if (streamRunning.value) stopStream()
  else startStream()
}

onBeforeUnmount(() => stopStream())
</script>

<template>
  <div>
    <el-tabs
      v-model="activeTab"
      class="log-tabs"
    >
      <el-tab-pane
        label="日志查看"
        name="viewer"
      >
        <div class="c-panel pad filter-bar">
          <el-select
            v-model="level"
            placeholder="全部级别"
            clearable
            style="width: 130px"
            :disabled="source === 'audit'"
            @change="page = 1; load()"
          >
            <el-option
              v-for="lv in ['debug', 'info', 'warning', 'error', 'critical']"
              :key="lv"
              :label="lv"
              :value="lv"
            />
          </el-select>
          <el-input
            v-model="keyword"
            :placeholder="source === 'audit' ? '操作者 / 成果ID / trace_id' : '消息 / trace_id'"
            style="width: 240px"
            clearable
            @keyup.enter="reloadFromFirst"
            @clear="reloadFromFirst"
          />
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 240px"
          />
          <el-button
            type="primary"
            :icon="Search"
            @click="reloadFromFirst"
          >
            查询
          </el-button>
          <span class="spacer" />
          <el-radio-group
            :model-value="source"
            size="small"
            @update:model-value="switchSource($event as 'audit' | 'system')"
          >
            <el-radio-button value="audit">
              审核留痕
            </el-radio-button>
            <el-radio-button value="system">
              系统事件
            </el-radio-button>
          </el-radio-group>
        </div>

        <div
          v-loading="loading"
          class="c-panel log-stream"
        >
          <div
            v-if="!rows.length"
            class="empty-state"
          >
            暂无日志记录
          </div>
          <div
            v-for="r in rows"
            :key="String(r.id)"
            class="log-line mono-data"
          >
            <template v-if="source === 'audit'">
              <span class="log-time">{{ fmtTime(r.created_at) }}</span>
              <span class="lv-tag">{{ ACTION_LABELS[Number(r.action_type)] ?? ('action ' + r.action_type) }}</span>
              <span class="log-main">{{ r.operator_name }}({{ r.operator_code }})</span>
              <span class="log-sub">成果 #{{ r.achievement_id }}{{ r.achievement_kind ? ' · ' + r.achievement_kind : '' }}<template v-if="r.trace_id"> · {{ r.trace_id }}</template></span>
            </template>
            <template v-else>
              <span class="log-time">{{ fmtTime(r.created_at) }}</span>
              <span
                class="lv-tag"
                :class="LEVEL_CLASS[String(r.event_level)] ?? ''"
              >{{ r.event_level }}</span>
              <span class="log-main">{{ r.event_message }}</span>
              <span class="log-sub">{{ r.event_category }}<template v-if="r.source_module"> · {{ r.source_module }}</template><template v-if="r.trace_id"> · {{ r.trace_id }}</template></span>
            </template>
          </div>
          <div class="stream-foot">
            <span class="status">共 {{ total }} 条</span>
            <el-pagination
              layout="prev, pager, next"
              small
              :total="total"
              :page-size="size"
              :current-page="page"
              @current-change="(p: number) => { page = p; load() }"
            />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="分析看板"
        name="dashboard"
        lazy
      >
        <div class="c-panel">
          <el-empty description="分析看板(六图)按批次迁移中——数据链路同 v1 admin_logs" />
        </div>
      </el-tab-pane>
      <el-tab-pane
        label="行动计划"
        name="plan"
        lazy
      >
        <div class="c-panel">
          <el-empty description="行动计划迁移中" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="实时流" name="stream" lazy>
        <div class="c-panel pad stream-head">
          <el-button
            :type="streamRunning ? 'warning' : 'primary'"
            data-testid="stream-toggle"
            @click="toggleStream"
          >
            {{ streamRunning ? '⏸ 暂停' : '▶ 开始实时流' }}
          </el-button>
          <span class="muted-xs">
            {{ streamRunning ? '连接中,每 2 秒推送系统事件增量' : '已断开(点击开始)' }};应用日志(文件)属 v1 资产不迁移。
          </span>
        </div>
        <div ref="streamEl" class="c-panel log-stream" :data-running="streamRunning">
          <div v-if="!streamLines.length" class="empty-state">
            {{ streamRunning ? '等待新事件…' : '点击上方开始按钮接入实时流' }}
          </div>
          <div v-for="line in streamLines" :key="line.id" class="log-line mono-data">
            <span class="log-time">{{ line.time }}</span>
            <span class="lv-tag" :class="LEVEL_CLASS[line.level] ?? ''">{{ line.level }}</span>
            <span class="log-main">{{ line.message }}</span>
            <span class="log-sub">{{ line.category }}<template v-if="line.module"> · {{ line.module }}</template></span>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.filter-bar .spacer { margin-left: auto; }
.log-stream { min-height: 320px; padding: 8px 0; }
.log-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 16px;
  font-size: 0.8rem;
  border-bottom: 1px solid var(--sb-line);
}
.log-line:hover { background: color-mix(in srgb, var(--brand) 4%, transparent); }
.log-time { color: var(--ink-2); flex-shrink: 0; }
.lv-tag {
  flex-shrink: 0;
  font-size: 0.72rem;
  padding: 1px 8px;
  border-radius: 4px;
  background: var(--sev-info-bg);
  color: var(--sev-info);
  font-weight: 600;
}
.lv-tag.lv-warning { background: var(--sev-warning-bg); color: var(--sev-warning); }
.lv-tag.lv-error { background: var(--sev-error-bg); color: var(--sev-error); }
.lv-tag.lv-critical { background: var(--sev-critical-bg); color: var(--sev-critical); }
.lv-tag.lv-debug { background: color-mix(in srgb, var(--ink) 6%, transparent); color: var(--ink-2); }
.log-main { color: var(--ink); }
.log-sub { color: var(--ink-2); font-size: 0.74rem; }
.stream-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid var(--line);
}
.status { font-size: 0.78rem; color: var(--ink-2); }
.mono-data { font-variant-numeric: tabular-nums; }
.stream-head {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
}
.muted-xs { font-size: 0.75rem; color: var(--ink-2); }
</style>
