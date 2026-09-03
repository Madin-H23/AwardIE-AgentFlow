<script setup lang="ts">
// UX-1 批1:表格加载骨架——列表页在 loading 时替换 v-loading 裸转圈(接入推广在 UX-1 批3)。
withDefaults(defineProps<{ rows?: number }>(), { rows: 6 })
</script>

<template>
  <div class="table-skeleton">
    <el-skeleton
      :rows="rows"
      animated
    />
  </div>
</template>

<style scoped>
.table-skeleton {
  padding: 8px 4px;
}
</style>
