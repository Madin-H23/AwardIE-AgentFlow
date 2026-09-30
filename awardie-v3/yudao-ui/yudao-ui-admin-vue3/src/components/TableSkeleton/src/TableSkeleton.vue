<script setup lang="ts">
// UX-1 移植(批28 D-12):表格加载骨架——v2 里是零引用孤儿,本批在 v3 反向真正接入:
// 列表页 loading 时替换 v-loading 裸转圈(已替换既有 4 处 ad-hoc el-skeleton)。
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
