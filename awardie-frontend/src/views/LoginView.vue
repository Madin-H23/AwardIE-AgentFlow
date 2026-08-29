<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ account: '', password: '' })

// 骨架占位:仅本地 dev 登录(P0 无后端);T4 接 Spring Security 后替换
async function onSubmit() {
  if (!form.account || !form.password) {
    ElMessage.warning('请输入账号与密码')
    return
  }
  loading.value = true
  await new Promise((r) => setTimeout(r, 300))
  auth.devLogin(form.account, form.account.startsWith('T') ? 'teacher' : 'student')
  loading.value = false
  ElMessage.success('dev 登录(未接后端)')
  router.push({ name: 'home' })
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="login-title">
        AwardIE
      </h1>
      <p class="login-sub">
        成果管理 · v2
      </p>
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="账号">
          <el-input
            v-model="form.account"
            placeholder="学号 / 工号"
            data-testid="login-account"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            data-testid="login-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          data-testid="login-submit"
          @click="onSubmit"
        >
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg);
}
.login-card { width: 360px; background: var(--panel); }
.login-title { margin: 0; text-align: center; color: var(--ink); letter-spacing: 2px; }
.login-sub { margin: 4px 0 16px; text-align: center; color: var(--ink-2); font-size: 13px; }
.login-btn { width: 100%; }
</style>
