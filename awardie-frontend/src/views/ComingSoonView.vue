<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Box } from '@element-plus/icons-vue'

// 侧边栏全量对照 v1 菜单的占位页:未迁移功能在此落点,不撒谎不留死链。
const route = useRoute()
const title = computed(() => String(route.query.title ?? '该功能'))
</script>

<template>
  <div class="soon">
    <div class="c-panel soon-panel">
      <el-icon
        :size="44"
        class="icon"
      >
        <Box />
      </el-icon>
      <h1>{{ title }} · 迁移中</h1>
      <p>
        该功能在 v1 控制台中存在,正按批次迁移至 v2 纵切面。
      </p>
      <p class="sub">
        迁移完成前可在 v1(127.0.0.1:5001)继续使用对应页面。
      </p>
      <router-link
        to="/"
        class="back"
      >
        返回工作台
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.soon { padding-top: 8vh; }
.soon-panel {
  max-width: 520px;
  margin: 0 auto;
  padding: 40px 32px;
  text-align: center;
}
.icon { color: var(--brand); }
h1 {
  font-size: 1.2rem;
  margin: 14px 0 10px;
  color: var(--ink);
}
p {
  color: var(--ink-2);
  font-size: 0.88rem;
  margin: 6px 0;
}
.sub { font-size: 0.78rem; }
.back {
  display: inline-block;
  margin-top: 16px;
  color: var(--brand);
  text-decoration: none;
  font-size: 0.88rem;
}
</style>
