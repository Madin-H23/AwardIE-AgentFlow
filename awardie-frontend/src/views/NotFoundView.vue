<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'

// Fix-U:catch-all 兜底页——此前未匹配路由渲染空白(巡检 low UX ①)。
// 无壳独立页;仅登录用户可达(守卫先拦未登录),返回首页经守卫按角色落位。
</script>

<template>
  <div class="nf">
    <div class="nf-panel">
      <el-icon
        :size="44"
        class="icon"
      >
        <QuestionFilled />
      </el-icon>
      <h1>404</h1>
      <p>页面不存在或已被移动。</p>
      <router-link
        to="/"
        class="back"
      >
        返回首页
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.nf {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nf-panel {
  max-width: 420px;
  padding: 48px 32px;
  text-align: center;
  background: var(--panel, #fff);
  border-radius: 10px;
}
.icon { color: var(--brand); }
h1 {
  font-size: 2.4rem;
  margin: 12px 0 8px;
  color: var(--ink);
  letter-spacing: 2px;
}
p {
  color: var(--ink-2);
  font-size: 0.88rem;
  margin: 6px 0 16px;
}
.back {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.88rem;
}
</style>
