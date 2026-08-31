<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// #33 对照 v1 assistant/chat_console.html+partials/_chat_content.html:
// chat-head(标题+模式 tabs)/mode-panel 引导卡(推荐问题 chips)/chat-messages 会话区/composer 输入条。
// SSE 打字机复用 teacher-review ai-suggest 模式(node/delta/final 事件)。

interface Msg {
  role: 'assistant' | 'user'
  text: string
  done?: boolean
}
const messages = ref<Msg[]>([{
  role: 'assistant',
  text: '你好!我是竞赛与奖状管理智能助手,可以帮你:知识问答(哪些是白名单赛事?)、数据查询、统计分析、导出报表。',
  done: true,
}])
const input = ref('')
const streaming = ref(false)
const messagesEl = ref<HTMLDivElement>()

const EXAMPLES = ['哪些是白名单赛事?', '挑战杯是几类竞赛?', '哪些竞赛贡献的奖状最多?']

function scrollBottom() {
  nextTick(() => messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight }))
}

function send(text?: string) {
  const q = (text ?? input.value).trim()
  if (!q || streaming.value) return
  messages.value.push({ role: 'user', text: q })
  input.value = ''
  const ai: Msg = { role: 'assistant', text: '', done: false }
  messages.value.push(ai)
  streaming.value = true
  scrollBottom()

  const es = new EventSource(`/api/v2/chat/stream?q=${encodeURIComponent(q)}`, { withCredentials: true })
  es.addEventListener('node', (e) => {
    const evt = JSON.parse((e as MessageEvent).data)
    ai.text += `\n[节点 ${evt.node}]\n`
    scrollBottom()
  })
  es.addEventListener('delta', (e) => {
    const evt = JSON.parse((e as MessageEvent).data)
    ai.text += evt.text
    scrollBottom()
  })
  es.addEventListener('final', (e) => {
    const evt = JSON.parse((e as MessageEvent).data)
    if (evt.code === 0) {
      if (evt.message) ai.text += evt.message
      ai.done = true
    } else {
      ai.text += evt.message || '回答失败'
      ai.done = true
    }
    streaming.value = false
    es.close()
    scrollBottom()
  })
  es.onerror = () => {
    ai.text += ai.text ? '\n(流中断)' : 'AI 服务不可用'
    ai.done = true
    streaming.value = false
    es.close()
    ElMessage.error('AI 回答流中断')
  }
}

function clearChat() {
  if (streaming.value) {
    ElMessage.warning('回答进行中,请稍候')
    return
  }
  messages.value = messages.value.slice(0, 1)
}
</script>

<template>
  <div class="chat-container">
    <div class="chat-head">
      <h1>🤖 AI 智能助手</h1>
      <el-button
        size="small"
        text
        data-testid="chat-clear"
        @click="clearChat"
      >
        🧹 清空对话
      </el-button>
    </div>

    <div class="mode-panel c-panel pad">
      <div class="panel-title">
        试试这些问题
      </div>
      <div class="chips">
        <el-tag
          v-for="ex in EXAMPLES"
          :key="ex"
          class="chip"
          @click="send(ex)"
        >
          {{ ex }}
        </el-tag>
      </div>
    </div>

    <div
      ref="messagesEl"
      class="chat-messages"
      data-testid="chat-messages"
    >
      <div
        v-for="(m, i) in messages"
        :key="i"
        class="msg"
        :class="m.role"
      >
        <div class="avatar">
          {{ m.role === 'assistant' ? '🤖' : '👤' }}
        </div>
        <div class="bubble">
          {{ m.text }}<span
            v-if="!m.done"
            class="cursor"
          >▍</span>
        </div>
      </div>
    </div>

    <div class="composer">
      <el-input
        v-model="input"
        placeholder="输入你的问题..."
        :disabled="streaming"
        data-testid="chat-input"
        @keyup.enter="send()"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :disabled="streaming || !input.trim()"
        data-testid="chat-send"
        @click="send()"
      >
        发送
      </el-button>
    </div>
    <p class="disclaimer">
      AI 回答仅辅助参考(BR-2);知识问答基于 RAG 检索,数据操作类能力随导入通道迁移后开放。
    </p>
  </div>
</template>

<style scoped>
.chat-container {
  max-width: 860px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 130px);
}
.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.chat-head h1 { margin: 0; }
.mode-panel { margin-bottom: 10px; }
.panel-title {
  font-size: 0.82rem;
  color: var(--ink-2);
  margin-bottom: 8px;
}
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { cursor: pointer; }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
}
.msg {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.msg.user { flex-direction: row-reverse; }
.avatar { font-size: 1.3rem; }
.bubble {
  max-width: 76%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 0.88rem;
  line-height: 1.7;
  white-space: pre-wrap;
  background: color-mix(in srgb, var(--ink) 5%, var(--panel));
  border: 1px solid var(--line);
  color: var(--ink);
}
.msg.assistant .bubble { border-top-left-radius: 2px; }
.msg.user .bubble {
  background: color-mix(in srgb, var(--brand) 10%, var(--panel));
  border-top-right-radius: 2px;
}
.cursor { animation: blink 0.9s infinite; color: var(--brand); }
@keyframes blink { 50% { opacity: 0; } }
.composer {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
.disclaimer {
  font-size: 0.72rem;
  color: var(--ink-2);
  margin: 8px 0 0;
}
</style>
