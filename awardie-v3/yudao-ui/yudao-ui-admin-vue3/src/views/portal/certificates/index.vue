<template>
  <div class="portal-page">
    <el-alert
      v-if="!loading && list.length === 0"
      type="info"
      :closable="false"
      title="还没有已通过的成果。提交后经教师审核通过,证书会出现在这里。"
    />

    <div v-for="item in list" :key="item.id" class="cert-card">
      <div class="cert-head">
        <el-tag :type="typeTone(item.achievementType)" size="small">
          {{ typeLabel(item.achievementType) }}
        </el-tag>
        <el-tag v-if="item.filePath" type="success" size="small" class="ml-6px">有证书</el-tag>
      </div>
      <div class="cert-title">{{ titleOf(item) }}</div>
      <div class="cert-meta">
        <span>{{ item.reviewTime || item.submitTime || '' }}</span>
      </div>

      <div v-loading="loadingId === item.id" class="cert-preview">
        <img
          v-if="urls[item.id]"
          :src="urls[item.id]"
          class="cert-img"
          alt="证书"
          @click="preview(item)"
        />
        <el-empty
          v-else-if="loadedId === item.id"
          description="证书加载失败"
          :image-size="50"
        />
        <el-skeleton v-else :rows="2" animated />
      </div>

      <div class="cert-actions">
        <el-button link type="primary" :disabled="!urls[item.id]" @click="preview(item)">
          查看大图
        </el-button>
        <el-button link type="primary" :loading="downloadingId === item.id" @click="handleSave(item)">
          保存到本地
        </el-button>
      </div>
    </div>

    <el-image-viewer v-if="viewerVisible" :url-list="[viewerUrl]" @close="viewerVisible = false" />
  </div>
</template>

<script setup lang="ts">
import download from '@/utils/download'
import { downloadPending, getMyPendingPage } from '@/api/business/achievement'

defineOptions({ name: 'PortalCertificates' })


const TYPES = [
  { value: 'award', label: '奖状' },
  { value: 'patent', label: '专利' },
  { value: 'software', label: '软著' },
  { value: 'innovation', label: '大创' },
  { value: 'other', label: '其他文件' }
]

const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v || '-'
const typeTone = (v: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  ({ award: 'primary', patent: 'success', software: 'warning', innovation: 'info' } as const)[v] || 'danger'

const titleOf = (item: any) => {
  if (!item.achievementData) {
    return `成果 #${item.id}`
  }
  try {
    const d = JSON.parse(item.achievementData)
    const key =
      ['competition_name', 'patent_name', 'software_name', 'project_name', 'file_name'].find((k) => d[k]) ||
      Object.keys(d)[0]
    return d[key] || `成果 #${item.id}`
  } catch {
    return `成果 #${item.id}`
  }
}

const loading = ref(false)
const list = ref<any[]>([])
/** id -> objectURL。证书图必须走 blob:鉴权走 Authorization 头,裸 <img src> 必然 401 */
const urls = reactive<Record<number, string>>({})
const loadingId = ref<number>()
const loadedId = ref<number>()
const downloadingId = ref<number>()

const getList = async () => {
  loading.value = true
  try {
    // 只看已通过(status=archived)的,那才是拿到证书的
    const data = await getMyPendingPage({ pageNo: 1, pageSize: 50, status: 'archived' })
    list.value = data.list || []
    for (const item of list.value) {
      if (item.filePath && !urls[item.id]) {
        await loadCert(item)
      }
    }
  } finally {
    loading.value = false
  }
}

const loadCert = async (item: any) => {
  loadingId.value = item.id
  try {
    const blob = await downloadPending(item.id)
    urls[item.id] = URL.createObjectURL(blob)
  } catch {
    // 加载不了就显示空态,不让整页崩
  } finally {
    loadedId.value = item.id
    loadingId.value = undefined
  }
}

const viewerVisible = ref(false)
const viewerUrl = ref('')

const preview = (item: any) => {
  if (!urls[item.id]) {
    return
  }
  viewerUrl.value = urls[item.id]
  viewerVisible.value = true
}

const handleSave = async (item: any) => {
  downloadingId.value = item.id
  try {
    const blob = await downloadPending(item.id)
    const ext = item.filePath?.includes('.') ? item.filePath.split('.').pop() : 'png'
    download.excel(blob, `证书-${item.id}.${ext}`)
  } finally {
    downloadingId.value = undefined
  }
}

onMounted(getList)
onBeforeUnmount(() => {
  for (const id of Object.keys(urls)) {
    URL.revokeObjectURL(urls[id as unknown as number])
  }
})
</script>

<style scoped>
.portal-page {
  max-width: 720px;
  margin: 0 auto;
}
.cert-card {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgb(0 0 0 / 6%);
}
.cert-head {
  display: flex;
  align-items: center;
}
.cert-title {
  margin-top: 8px;
  font-size: 15px;
  font-weight: 500;
  word-break: break-all;
}
.cert-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.cert-preview {
  margin-top: 10px;
}
.cert-img {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  cursor: zoom-in;
}
.cert-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}
.cert-actions :deep(.el-button) {
  min-height: 44px;
  padding: 0 8px;
}
</style>
