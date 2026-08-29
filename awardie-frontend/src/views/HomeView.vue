<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="home">
    <h2>v2 首页(骨架占位)</h2>
    <p>当前用户:<b>{{ auth.username }}</b> · 角色:{{ auth.role ?? '-' }}</p>
    <p>纵切面链路(登录→提交→AI 审核→时间线)由 T5-T9 逐张接入。</p>
    <el-button @click="logout">
      登出
    </el-button>
  </div>
</template>

<style scoped>
.home { max-width: 720px; margin: 48px auto; padding: 24px; background: var(--panel); border-radius: 8px; }
</style>
