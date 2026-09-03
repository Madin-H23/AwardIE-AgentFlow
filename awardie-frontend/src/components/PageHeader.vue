<script setup lang="ts">
// UX-1 批1:统一页头(签名元素"页面节奏"三段式的第一段)——标题+副标题+右侧操作区。
// type scale 见 tokens.css --fs-*;后续批次逐页替换裸 h2 页头。
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
      <slot name="actions" />
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
  color: var(--ink);
  margin: 0;
  line-height: 1.3;
}
.ph-sub {
  margin: 4px 0 0;
  font-size: var(--fs-cap);
  color: var(--ink-2);
}
.ph-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>
