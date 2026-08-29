<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="home">
    <h2>v2 首页(骨架占位)</h2>
    <p v-if="auth.user">
      当前用户:<b>{{ auth.user.name }}</b> · 角色:{{ auth.user.role }} · 学工号:{{ auth.user.id }}
    </p>
    <p>纵切面链路(提交→AI 审核→时间线)由 T5-T9 逐张接入。</p>
    <el-button
      data-testid="logout"
      @click="logout"
    >
      登出
    </el-button>
  </div>
</template>

<style scoped>
.home { max-width: 720px; margin: 48px auto; padding: 24px; background: var(--panel); border-radius: 8px; }
</style>
