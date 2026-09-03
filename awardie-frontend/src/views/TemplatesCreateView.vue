<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// Fix-TP 对照 v1 admin/templates/tabs/create.html:创建模板(样本图/竞赛/角色/字段配置)。
// 架构票交付物 5(页面批次):AI 抽取/生成提示词接 extract-for-create 与 generate-prompt-for-create 主链(fake/grpc 随 ai.worker.mode)。

interface Competition { id: number; competitionName: string }

const router = useRouter()
const competitions = ref<Competition[]>([])
const saving = ref(false)
const form = reactive({
  competitionId: null as number | null,
  grantedRole: '学生',
  competitionName: '',
  language: 'zh',
  needTranslate: false,
  minLength: 0,
  maxLength: null as number | null,
  keywords: '',
  sampleText: '',
  sampleExtracted: '{}',
  defaultFields: '{}',
  llmFields: '{}',
})
const sampleFile = ref<File | null>(null)
const samplePreview = ref('')
const extracting = ref(false)
const prompting = ref(false)
const extractMode = ref('')
const promptMode = ref('')
const promptResult = ref('')

function onSampleChange(file: UploadFile) {
  sampleFile.value = file.raw as File
  samplePreview.value = URL.createObjectURL(file.raw as File)
}

onMounted(async () => {
  const body = await apiJson('GET', '/api/v2/admin/competitions?page=1&size=100')
  if (body.code === 0) competitions.value = body.data.content
})

async function postForm(path: string, fd: FormData) {
  const token = document.cookie.match(/(?:^|; )XSRF-TOKEN=([^;]*)/)
  const resp = await fetch(path, {
    method: 'POST', body: fd, credentials: 'include',
    headers: token ? { 'X-XSRF-TOKEN': decodeURIComponent(token[1]) } : {},
  })
  return resp.json()
}

/** AI 抽取:样本图 → extract-for-create,回填样本抽取值/样本文本(样本文本留空时)。 */
async function aiExtract() {
  if (!sampleFile.value) return ElMessage.warning('请先上传样本图片')
  extracting.value = true
  try {
    const fd = new FormData()
    fd.append('file', sampleFile.value)
    const body = await postForm('/api/v2/admin/templates/extract-for-create', fd)
    if (body.code === 0) {
      extractMode.value = body.data.mode
      try {
        form.sampleExtracted = JSON.stringify(JSON.parse(body.data.dataJson), null, 2)
      } catch {
        form.sampleExtracted = body.data.dataJson
      }
      if (!form.sampleText.trim()) form.sampleText = body.data.ocrText ?? ''
      ElMessage.success('抽取完成,已回填样本抽取值')
    } else {
      ElMessage.error(body.message ?? '抽取失败')
    }
  } finally {
    extracting.value = false
  }
}

/** 生成提示词:表单规则 → generate-prompt-for-create,预览 prompt。 */
async function genPrompt() {
  prompting.value = true
  try {
    const body = await apiJson('POST', '/api/v2/admin/templates/generate-prompt-for-create', {
      keywords: form.keywords.split('\n').map((k) => k.trim()).filter(Boolean),
      sample_extracted: safeParse(form.sampleExtracted),
      default_fields: safeParse(form.defaultFields),
      llm_fields: safeParse(form.llmFields),
      min_length: form.minLength ?? 0,
      max_length: form.maxLength ?? 0,
      language: form.language,
      need_translate: form.needTranslate,
      sample_text: form.sampleText,
    })
    if (body.code === 0) {
      promptMode.value = body.data.mode
      promptResult.value = body.data.prompt
      ElMessage.success('提示词已生成')
    } else {
      ElMessage.error(body.message ?? '生成失败')
    }
  } finally {
    prompting.value = false
  }
}

async function save() {
  if (!form.competitionId) return ElMessage.warning('请选择竞赛')
  if (!sampleFile.value) return ElMessage.warning('请上传样本图片')
  for (const [label, text] of [['样本抽取值', form.sampleExtracted], ['默认字段', form.defaultFields], ['LLM 字段', form.llmFields]] as const) {
    try { if (text.trim()) JSON.parse(text) } catch {
      return ElMessage.warning(`${label} 不是合法 JSON`)
    }
  }
  saving.value = true
  try {
    const fd = new FormData()
    fd.append('file', sampleFile.value)
    fd.append('competitionId', String(form.competitionId))
    fd.append('grantedRole', form.grantedRole)
    fd.append('sampleExtracted', form.sampleExtracted || '{}')
    fd.append('sampleText', form.sampleText)
    fd.append('keywords', form.keywords)
    fd.append('language', form.language)
    fd.append('needTranslate', String(form.needTranslate))
    fd.append('minLength', String(form.minLength ?? 0))
    if (form.maxLength != null) fd.append('maxLength', String(form.maxLength))
    fd.append('defaultFields', form.competitionName
      ? JSON.stringify({ ...safeParse(form.defaultFields), competition_name: form.competitionName })
      : form.defaultFields || '{}')
    fd.append('llmFields', form.llmFields || '{}')
    const body = await postForm('/api/v2/admin/templates/create', fd)
    if (body.code === 0) {
      ElMessage.success('模板已创建')
      router.push(`/admin/templates/${body.data}/detail`)
    } else {
      ElMessage.error(body.message ?? '创建失败')
    }
  } finally {
    saving.value = false
  }
}

function safeParse(text: string): Record<string, unknown> {
  try { return JSON.parse(text) } catch { return {} }
}
</script>

<template>
  <div>
    <div class="page-head">
      <h1>创建模板</h1>
      <div>
        <el-button
          type="primary"
          data-testid="tpl-create-save"
          @click="save"
        >
          保存
        </el-button>
        <el-button @click="router.push('/admin/templates')">
          返回列表
        </el-button>
      </div>
    </div>

    <div class="grid-2">
      <div class="c-panel pad">
        <h3 class="blk-title">
          基本信息
        </h3>
        <div class="frm">
          <label>竞赛 <span class="req">*</span></label>
          <el-select
            v-model="form.competitionId"
            filterable
            data-testid="tpl-create-competition"
          >
            <el-option
              v-for="c in competitions"
              :key="c.id"
              :value="c.id"
              :label="c.competitionName"
            />
          </el-select>
          <label>授予角色 <span class="req">*</span></label>
          <el-radio-group v-model="form.grantedRole">
            <el-radio-button value="学生">
              学生
            </el-radio-button>
            <el-radio-button value="教师">
              教师
            </el-radio-button>
          </el-radio-group>
          <label>上传奖状图片 <span class="req">*</span></label>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept="image/*"
            :on-change="onSampleChange"
            data-testid="tpl-create-image"
          >
            <el-button>选择图片</el-button>
          </el-upload>
          <div class="row-2">
            <el-button
              :loading="extracting"
              data-testid="tpl-ai-extract"
              @click="aiExtract"
            >
              AI 抽取
            </el-button>
            <el-tag
              v-if="extractMode"
              size="small"
              type="info"
            >
              {{ extractMode }}
            </el-tag>
          </div>
          <img
            v-if="samplePreview"
            :src="samplePreview"
            class="preview"
            alt="样本预览"
          >
        </div>
      </div>

      <div class="c-panel pad">
        <h3 class="blk-title">
          详细配置
        </h3>
        <div class="frm">
          <label>竞赛名称(默认取所选竞赛)</label>
          <el-input
            v-model="form.competitionName"
            placeholder="可输入,留空用所选竞赛名"
          />
          <label>语言</label>
          <el-radio-group v-model="form.language">
            <el-radio-button value="zh">
              中文
            </el-radio-button>
            <el-radio-button value="en">
              英文
            </el-radio-button>
          </el-radio-group>
          <el-checkbox v-model="form.needTranslate">
            翻译成中文
          </el-checkbox>
          <label>长度区间</label>
          <div class="row-2">
            <el-input-number
              v-model="form.minLength"
              :min="0"
              controls-position="right"
              placeholder="最小"
            />
            <el-input-number
              v-model="form.maxLength"
              :min="0"
              controls-position="right"
              placeholder="无限制"
            />
          </div>
          <label>角色 &amp; 关键词(每行一个)</label>
          <el-input
            v-model="form.keywords"
            type="textarea"
            :rows="2"
            placeholder="留空默认用竞赛名"
          />
          <label>样本文本</label>
          <el-input
            v-model="form.sampleText"
            type="textarea"
            :rows="4"
          />
          <label>样本抽取值(JSON)</label>
          <el-input
            v-model="form.sampleExtracted"
            type="textarea"
            :rows="3"
            data-testid="tpl-create-extracted"
          />
          <label>默认字段(JSON,高级)</label>
          <el-input
            v-model="form.defaultFields"
            type="textarea"
            :rows="2"
          />
          <label>LLM 字段(JSON,高级)</label>
          <el-input
            v-model="form.llmFields"
            type="textarea"
            :rows="2"
          />
        </div>
      </div>
    </div>

    <div class="c-panel pad mt-3">
      <h3 class="blk-title">
        提示词模板与测试
      </h3>
      <div class="frm">
        <div class="row-2">
          <el-button
            type="primary"
            :loading="prompting"
            data-testid="tpl-ai-prompt"
            @click="genPrompt"
          >
            生成提示词
          </el-button>
          <el-tag
            v-if="promptMode"
            size="small"
            type="info"
          >
            {{ promptMode }}
          </el-tag>
        </div>
        <el-input
          v-if="promptResult"
          :model-value="promptResult"
          type="textarea"
          :rows="8"
          readonly
          data-testid="tpl-prompt-preview"
        />
        <p
          v-else
          class="muted small"
        >
          按当前表单规则生成提示词预览;创建后可在详情页试测。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.blk-title { margin: 0 0 12px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.frm { display: flex; flex-direction: column; gap: 6px; }
.frm label { font-size: 0.82rem; color: var(--ink-2); }
.req { color: #ef4444; }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.preview { max-width: 100%; max-height: 200px; border: 1px solid var(--line); border-radius: 6px; }
.mt-3 { margin-top: 14px; }
.muted { color: var(--ink-2); }
.small { font-size: 0.8rem; }
</style>
