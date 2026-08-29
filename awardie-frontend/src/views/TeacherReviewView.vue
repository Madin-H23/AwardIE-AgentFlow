<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

const API = '/api/v2'
const rows = ref<Array<Record<string, unknown>>>([])
const aiText = ref('')
const aiRunning = ref(false)
const aiId = ref<number | null>(null)
const rejectComment = ref('')
const rejectId = ref<number | null>(null)

async function load() {
  const resp = await fetch(`${API}/teacher/pending`, { credentials: 'include' })
  const body = (await resp.json()) as { code: number; data?: Array<Record<string, unknown>> }
  rows.value = body.code === 0 ? (body.data ?? []) : []
}
onMounted(load)

/** AI 建议:SSE 流式(node/delta/final),打字机累积;降级 4003 显示人工审提示。 */
function aiSuggest(id: number) {
  aiId.value = id
  aiText.value = ''
  aiRunning.value = true
  fetch(`${API}/teacher/review/${id}/ai-suggest`, { credentials: 'include' }).then(async (resp) => {
    const reader = resp.body!.getReader()
    const dec = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() ?? ''
      for (const part of parts) {
        const line = part.split('\n').find((l) => l.startsWith('data:'))
        if (!line) continue
        try {
          const evt = JSON.parse(line.slice(5).trim())
          if (evt.kind === 'node') aiText.value += `\n[节点 ${evt.node}]\n`
          else if (evt.kind === 'delta') aiText.value += evt.text
          else if (evt.kind === 'final') {
            aiText.value += `\n\n结论:${(evt.message ?? '').split('|')[0]}`
            if (evt.code === 4003) aiText.value += `\n${evt.message}`
            aiText.value += `\n${evt.disclaimer ?? ''}`
          }
        } catch { /* 非 JSON 心跳忽略 */ }
      }
    }
    aiRunning.value = false
  }).catch(() => { aiRunning.value = false; ElMessage.error('AI 建议流中断') })
}

async function review(id: number, action: string) {
  const comment = action === 'reject' ? rejectComment.value : '同意,材料齐全'
  const resp = await fetch(`${API}/teacher/review/${id}`, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, comment }),
  })
  const body = await resp.json()
  if (body.code === 0) {
    ElMessage.success(`已${action === 'approve' ? '批准' : '驳回'} #${id}`)
    rejectId.value = null
    rejectComment.value = ''
    await load()
  } else {
    ElMessage.error(body.message)
  }
}
</script>

<template>
  <div class="review-page">
    <el-card>
      <h2>待审列表(教师)</h2>
      <el-table
        :data="rows"
        size="small"
      >
        <el-table-column
          prop="id"
          label="#"
          width="70"
        />
        <el-table-column
          prop="achievementType"
          label="类型"
          width="90"
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
          label="AI 建议"
          width="110"
        >
          <template #default="scope">
            <el-button
              size="small"
              :loading="aiRunning && aiId === scope.row.id"
              @click="aiSuggest(scope.row.id)"
            >
              AI 建议
            </el-button>
          </template>
        </el-table-column>
        <el-table-column
          label="审核操作"
          min-width="220"
        >
          <template #default="scope">
            <el-button
              size="small"
              type="success"
              @click="review(scope.row.id, 'approve')"
            >
              批准
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
              placeholder="驳回原因(BR-5 必填)"
            />
          </template>
        </el-table-column>
      </el-table>
      <pre
        v-if="aiText"
        class="ai-box"
      >{{ aiText }}</pre>
    </el-card>
  </div>
</template>

<style scoped>
.review-page { max-width: 1100px; margin: 24px auto; }
h2 { margin-top: 0; color: var(--ink); }
.ai-box { white-space: pre-wrap; background: var(--sb-foot); padding: 12px; border-radius: 6px; max-height: 300px; overflow: auto; }
</style>
