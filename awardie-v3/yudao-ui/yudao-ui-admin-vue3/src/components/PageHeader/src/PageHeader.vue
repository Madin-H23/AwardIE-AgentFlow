<script setup lang="ts">
// UX-1 移植(批28 D-12):统一页头(标题+副标题+右侧操作区,签名元素"页面节奏"的第一段)。
// 颜色走 EP 文本变量自动适配暗色(替代 v2 原版的 --ink/--ink-2 token);字号走 --fs-*。
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <header class="page-header">
    <div class="ph-text">
      <h1 class="ph-title">
        {{ title }}
      </h1>
      <p
        v-if="subtitle"
        class="ph-sub"
      >
        {{ subtitle }}
      </p>
    </div>
    <div
      v-if="$slots.actions"
      class="ph-actions"
    >
      <slot name="actions"></slot>
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.ph-title {
  font-size: var(--fs-page);
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
  line-height: 1.3;
}
.ph-sub {
  margin: 4px 0 0;
  font-size: var(--fs-cap);
  color: var(--el-text-color-secondary);
}
.ph-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>
