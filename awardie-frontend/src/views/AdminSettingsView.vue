<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson } from '../composables/useCsrf'

// #32 对照 v1 admin/settings.html:三 tab(通用/供应商/自动归档)。
// 架构偏差:通用与供应商为只读信息卡(外部化配置走 application.yml/env);自动归档为真读写,见对照记录。
interface ArchiveRow {
  achievement_type: string
  validation_status: string | null
  auto_archive_enabled: boolean
}
const activeTab = ref('general')
const rows = ref<ArchiveRow[]>([])
const loading = ref(false)

const TYPE_LABELS: Record<string, string> = {
  award: '奖状', patent: '专利', software: '软著', innovation: '大创', other: '其他文件',
}

function rowFor(type: string, status: string | null): ArchiveRow | undefined {
  return rows.value.find(
    (r) => r.achievement_type === type && ((r.validation_status ?? null) === status),
  )
}

const MATRIX: Array<{ type: string; status: string | null }> = [
  { type: 'award', status: 'valid' },
  { type: 'award', status: 'invalid' },
  { type: 'patent', status: 'valid' },
  { type: 'patent', status: 'invalid' },
  { type: 'software', status: 'valid' },
  { type: 'software', status: 'invalid' },
  { type: 'innovation', status: null },
  { type: 'other', status: null },
]

async function load() {
  loading.value = true
  try {
    const body = await apiJson('GET', '/api/v2/admin/settings/auto-archive')
    if (body.code === 0) rows.value = body.data
  } finally {
    loading.value = false
  }
}

async function save() {
  const body = await apiJson('PUT', '/api/v2/admin/settings/auto-archive', { rows: rows.value })
  if (body.code === 0) ElMessage.success('已保存')
  else ElMessage.error(body.message)
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <h1>系统设置</h1>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane
        label="通用设置"
        name="general"
      >
        <div class="c-panel pad info-card">
          <h3 class="blk-title">
            系统默认密码
          </h3>
          <p>
            新建账号的默认口令与口令重置属<b>部署配置</b>(v2 由 application.yml / 环境变量管理),不在页面修改;
            兼容约束见 ADR-0002(v2 恒产 werkzeug scrypt 格式,v1/v2 双登录)。
          </p>
          <h3 class="blk-title">
            缓存清理
          </h3>
          <p>
            v2 纵切面暂无 OCR/抽取缓存表,该分区随对应功能迁移后开放。
          </p>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="供应商设置"
        name="providers"
      >
        <div class="c-panel pad info-card">
          <h3 class="blk-title">
            OCR / LLM 供应商
          </h3>
          <p>
            供应商与密钥属<b>外部化配置</b>(AI Worker 侧环境变量;Java 经 ai.worker.mode=gRPC 接入),页面不展示密钥明文。
            当前模式可在登录后由 /actuator/info 与部署清单核对。
          </p>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="自动归档"
        name="archive"
      >
        <div class="c-panel pad">
          <p class="hint">
            学生提交自动归档开关:开启后对应类型×校验状态的提交免人工审核直接入库(仅学生提交生效;v1 真语义:大创走 admin 导入通道)。
          </p>
          <el-table
            v-loading="loading"
            :data="MATRIX"
            size="default"
          >
            <el-table-column
              label="成果类型"
              width="140"
            >
              <template #default="scope">
                {{ TYPE_LABELS[scope.row.type] }}
              </template>
            </el-table-column>
            <el-table-column
              label="校验状态"
              width="140"
            >
              <template #default="scope">
                {{ scope.row.status ? (scope.row.status === 'valid' ? '校验通过' : '校验存疑') : '不区分' }}
              </template>
            </el-table-column>
            <el-table-column label="自动归档">
              <template #default="scope">
                <el-switch
                  v-if="rowFor(scope.row.type, scope.row.status)"
                  v-model="rowFor(scope.row.type, scope.row.status)!.auto_archive_enabled"
                />
              </template>
            </el-table-column>
          </el-table>
          <el-button
            type="primary"
            style="margin-top: 14px"
            data-testid="settings-save"
            @click="save"
          >
            保存
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.blk-title { margin: 0 0 8px; font-size: 1rem; font-weight: 600; color: var(--ink); }
.info-card p { font-size: 0.85rem; color: var(--ink-2); line-height: 1.8; }
.hint { font-size: 0.8rem; color: var(--ink-2); margin: 0 0 12px; }
</style>
