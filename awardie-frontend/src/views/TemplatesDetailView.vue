<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-TP 对照 v1 admin/templates/tabs/detail.html:模板详情/编辑+样本图回显+试测(fake 桩,01-方案 偏差1)。

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const loading = ref(true)
const testBusy = ref(false)
const testResult = ref<{ mode: string; fields: string; ocrText: string } | null>(null)
const form = reactive({
  minLength: 0,
  maxLength: 0,
  keywords: '',
  sampleText: '',
  sampleExtracted: '{}',
  defaultFields: '{}',
  llmFields: '{}',
  language: 'zh',
  needTranslate: false,
})
const hasImage = ref(false)
const competitionName = ref('')

function pretty(text: string | null): string {
  if (!text) return '{}'
  try { return JSON.stringify(JSON.parse(text), null, 2) } catch { return text }
}

onMounted(async () => {
  const body = await apiJson('GET', `/api/v2/admin/templates/${id}/detail`)
  if (body.code !== 0) {
    ElMessage.error(body.message ?? '模板不存在')
    loading.value = false
    return
  }
  const d = body.data
  Object.assign(form, {
    minLength: d.minLength ?? 0, maxLength: d.maxLength ?? 0,
    keywords: prettyJoin(d.keywords), sampleText: d.sampleText ?? '',
    sampleExtracted: pretty(d.sampleExtracted), defaultFields: pretty(d.defaultFields),
    llmFields: pretty(d.llmFields), language: d.language ?? 'zh',
    needTranslate: !!d.needTranslate,
  })
  hasImage.value = !!d.hasImage
  competitionName.value = d.competitionName ?? ''
  loading.value = false
})

function prettyJoin(text: unknown): string {
  try {
    const arr = typeof text === 'string' ? JSON.parse(text) : text
    return Array.isArray(arr) ? arr.join('\n') : String(text ?? '')
  } catch {
    return String(text ?? '')
  }
}

function toLines(text: string): string {
  return JSON.stringify(text.split('\n').map((s) => s.trim()).filter(Boolean))
}

async function save() {
  const body = await apiJson('PUT', `/api/v2/admin/templates/${id}`, {
    minLength: form.minLength,
    maxLength: form.maxLength,
    keywords: toLines(form.keywords),
    sampleText: form.sampleText,
    sampleExtracted: form.sampleExtracted,
    defaultFields: form.defaultFields,
    llmFields: form.llmFields,
    language: form.language,
    needTranslate: form.needTranslate,
  })
  if (body.code === 0) {
    ElMessage.success('模板已更新')
  } else {
    ElMessage.error(body.message ?? '更新失败')
  }
}

async function runTest() {
  testBusy.value = true
  try {
    const body = await apiJson('POST', `/api/v2/admin/templates/${id}/test`)
    if (body.code === 0) {
      testResult.value = {
        mode: body.data.mode,
        fields: pretty(body.data.fields),
        ocrText: body.data.ocrText ?? '',
      }
    } else {
      ElMessage.error(body.message ?? '试测失败')
    }
  } finally {
    testBusy.value = false
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-head">
      <h1>模板详情{{ competitionName ? ` - ${competitionName}` : ` #${id}` }}</h1>
      <div>
        <el-button type="primary" data-testid="tpl-detail-save" @click="save">保存</el-button>
        <el-button @click="router.push('/admin/templates')">返回列表</el-button>
      </div>
    </div>

    <div class="grid-2">
      <div class="c-panel pad">
        <h3 class="blk-title">基本信息</h3>
        <div class="frm">
          <label>语言</label>
          <el-radio-group v-model="form.language">
            <el-radio-button value="zh">中文</el-radio-button>
            <el-radio-button value="en">英文</el-radio-button>
          </el-radio-group>
          <el-checkbox v-model="form.needTranslate">翻译成中文</el-checkbox>
          <label>长度区间</label>
          <div class="row-2">
            <el-input-number v-model="form.minLength" :min="0" controls-position="right" />
            <el-input-number v-model="form.maxLength" :min="0" controls-position="right" />
          </div>
          <label>角色 &amp; 关键词(每行一个)</label>
          <el-input v-model="form.keywords" type="textarea" :rows="3" data-testid="tpl-detail-keywords" />
          <label>样本图片</label>
          <img
            v-if="hasImage" :src="`/api/v2/admin/templates/${id}/image`"
            class="preview" alt="样本图" data-testid="tpl-detail-image"
          >
          <p v-else class="muted small">无样本图</p>
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">抽取配置</h3>
        <div class="frm">
          <label>样本文本</label>
          <el-input v-model="form.sampleText" type="textarea" :rows="4" />
          <label>样本抽取值(JSON)</label>
          <el-input v-model="form.sampleExtracted" type="textarea" :rows="4" data-testid="tpl-detail-extracted" />
          <label>默认字段(JSON,高级)</label>
          <el-input v-model="form.defaultFields" type="textarea" :rows="3" />
          <label>LLM 字段(JSON,高级)</label>
          <el-input v-model="form.llmFields" type="textarea" :rows="3" />
        </div>
      </div>
    </div>

    <div class="c-panel pad mt-3">
      <h3 class="blk-title">提示词模板测试</h3>
      <el-button type="primary" plain :loading="testBusy" data-testid="tpl-test-run" @click="runTest">运行试测(fake)</el-button>
      <div v-if="testResult" class="mt-3" data-testid="tpl-test-result">
        <el-tag size="small" type="info">mode: {{ testResult.mode }}</el-tag>
        <p class="muted small mt-2">抽取字段:</p>
        <pre class="ocr-pre">{{ testResult.fields }}</pre>
        <p class="muted small mt-2">样本文本:</p>
        <pre class="ocr-pre">{{ testResult.ocrText }}</pre>
      </div>
      <p v-else class="muted small">试测走 fake 确定性桩(回显模板样本值);真 Extract RPC=架构票排期中。</p>
    </div>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.frm { display: flex; flex-direction: column; gap: 6px; }
.frm label { font-size: 0.82rem; color: var(--ink-2); }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.preview { max-width: 100%; max-height: 220px; border: 1px solid var(--line); border-radius: 6px; }
.mt-3 { margin-top: 14px; }
.mt-2 { margin-top: 8px; }
.muted { color: var(--ink-2); }
.small { font-size: 0.8rem; }
.ocr-pre { background: color-mix(in srgb, var(--ink) 4%, transparent); padding: 10px; border-radius: 6px; font-size: 0.78rem; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }
</style>
