<template>
  <div class="bulk-import">
    <ContentWrap>
      <el-alert type="info" :closable="false" class="mb-12px">
        <template #title>
          对齐 v1 批量导入:多选证书图片 → AI 逐张识别(可人工改)→ 勾选提交。
          提交人=当前管理员,与 v1 历史数据口径一致;提交后走正常审核队列。
          {{ aiMode === 'fake' ? '(当前 Worker 为 fake 模式,识别结果是确定性桩)' : '' }}
        </template>
      </el-alert>

      <el-upload
        :auto-upload="false"
        multiple
        accept=".jpg,.jpeg,.png,.pdf"
        :show-file-list="false"
        :on-change="onFilesAdded"
      >
        <el-button type="primary" icon="ep:upload-filled">选择证书图片(可多选)</el-button>
      </el-upload>
      <el-button
        v-if="rows.length"
        class="ml-8px"
        :loading="parsing"
        @click="parseAllPending"
      >
        识别未解析的 {{ rows.filter((r) => !r.parsed).length }} 张
      </el-button>
    </ContentWrap>

    <ContentWrap v-if="rows.length">
      <div class="mb-10px flex items-center justify-between">
        <span class="text-14px">
          共 {{ rows.length }} 张 | 已识别 {{ parsedCount }} | 已勾选 {{ selectedCount }}
        </span>
        <div>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="selectedCount === 0"
            @click="handleSubmitSelected"
          >
            提交所选({{ selectedCount }})
          </el-button>
          <el-button @click="rows = []">清空</el-button>
        </div>
      </div>

      <el-table :data="rows" border row-key="uid" empty-text="请先选择文件">
        <el-table-column width="50" align="center">
          <template #header>
            <el-checkbox
              :model-value="allParsedSelected"
              :disabled="parsedCount === 0"
              @change="toggleAll"
            />
          </template>
          <template #default="{ row }">
            <el-checkbox v-if="row.parsed" v-model="row.checked" />
            <el-checkbox v-else disabled />
          </template>
        </el-table-column>
        <el-table-column label="文件" prop="fileName" min-width="180" show-overflow-tooltip />
        <el-table-column label="识别" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.parsed && !row.error" type="success" size="small">已识别</el-tag>
            <el-tag v-else-if="row.parsed && row.error" type="danger" size="small">失败</el-tag>
            <el-tag v-else type="info" size="small">未识别</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成果类型" width="120" align="center">
          <template #default="{ row }">
            <el-select v-model="row.achievementType" size="small" :disabled="submittingRowUid === row.uid">
              <el-option v-for="t in TYPES" :key="t.value" :value="t.value" :label="t.label" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="关键信息(JSON)" min-width="280">
          <template #default="{ row }">
            <el-input
              v-model="row.dataJson"
              type="textarea"
              :rows="2"
              :disabled="submittingRowUid === row.uid"
              placeholder="识别后自动填入;JSON 键需与成果字段对齐"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.result === 'ok'" class="text-green-600">提交成功 #{{ row.pendingId }}</span>
            <span v-else-if="row.result === 'fail'" class="text-red-600">{{ row.resultMsg }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </ContentWrap>
  </div>
</template>

<script setup lang="ts">
/**
 * 管理员批量导入(批18,对齐 v1 file-import 的主路径):
 * 多文件 → 逐张调 /parse(fake 模式确定性桩,grpc 真实 OCR+LLM)→ 行内可改类型与
 * JSON 字段 → 勾选后逐条调 /submit。提交人=当前管理员(submitter_type=admin),
 * 与 v1 历史数据(V1 的 45 条待审全部 admin 提交)口径一致。
 * 后端零新端点:parse(批17)+ submit(批4)已覆盖全部需要。
 */
import { parsePending, submitPending } from '@/api/business/achievement'

defineOptions({ name: 'BulkImport' })

const message = useMessage()

const TYPES = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]

interface ImportRow {
  uid: number
  file: File
  fileName: string
  parsed: boolean
  error?: string
  achievementType: string
  dataJson: string
  checked: boolean
  result?: 'ok' | 'fail'
  resultMsg?: string
  pendingId?: number
}

const rows = ref<ImportRow[]>([])
const parsing = ref(false)
const submitting = ref(false)
const submittingRowUid = ref<number>()
const aiMode = ref('')

let uidSeq = 1

const parsedCount = computed(() => rows.value.filter((r) => r.parsed && !r.error).length)
const selectedCount = computed(() => rows.value.filter((r) => r.checked && r.parsed && !r.error).length)
const allParsedSelected = computed(
  () => parsedCount.value > 0 && rows.value.filter((r) => r.parsed && !r.error).every((r) => r.checked)
)

const onFilesAdded = (_: any, fileList: any) => {
  for (const f of fileList as any[]) {
    const raw: File = f.raw
    // 同名同大小的文件不重复加(el-upload 的 fileList 会累积)
    if (rows.value.some((r) => r.fileName === raw.name && r.file.size === raw.size)) {
      continue
    }
    rows.value.push({
      uid: uidSeq++,
      file: raw,
      fileName: raw.name,
      parsed: false,
      achievementType: 'award',
      dataJson: '',
      checked: false
    })
  }
  parseAllPending()
}

const parseAllPending = async () => {
  const pending = rows.value.filter((r) => !r.parsed)
  if (!pending.length) {
    return
  }
  parsing.value = true
  try {
    for (const row of pending) {
      try {
        const res: any = await parsePending(row.file)
        aiMode.value = res?.mode || aiMode.value
        row.dataJson = res?.dataJson || ''
        row.parsed = true
        row.checked = true
      } catch (e: any) {
        row.parsed = true
        row.error = e?.message || '识别失败'
      }
    }
    message.success(`识别完成:${parsedCount.value}/${rows.value.length} 张成功`)
  } finally {
    parsing.value = false
  }
}

const toggleAll = (checked: boolean) => {
  rows.value.forEach((r) => {
    if (r.parsed && !r.error) {
      r.checked = checked
    }
  })
}

const handleSubmitSelected = async () => {
  const targets = rows.value.filter((r) => r.checked && r.parsed && !r.error && r.result !== 'ok')
  if (!targets.length) {
    return
  }
  await message.confirm(`将提交 ${targets.length} 条待审成果(提交人=当前管理员),确认?`, '批量提交')
  submitting.value = true
  let ok = 0
  const failed: string[] = []
  try {
    for (const row of targets) {
      submittingRowUid.value = row.uid
      try {
        // JSON 合法性前置校验:后端只校验文件与类型,坏 JSON 会静默落成空 data
        JSON.parse(row.dataJson || '{}')
        const res: any = await submitPending(row.file, row.achievementType, row.dataJson || '{}')
        row.result = 'ok'
        row.pendingId = res?.id
        ok += 1
      } catch (e: any) {
        row.result = 'fail'
        row.resultMsg = e?.message || '提交失败'
        failed.push(row.fileName)
      }
    }
    if (failed.length) {
      message.warning(`成功 ${ok} 条,失败 ${failed.length} 条(见状态列)`)
    } else {
      message.success(`已提交 ${ok} 条`)
    }
  } finally {
    submitting.value = false
    submittingRowUid.value = undefined
  }
}
</script>

<style scoped>
.bulk-import {
  max-width: 1200px;
}
</style>
