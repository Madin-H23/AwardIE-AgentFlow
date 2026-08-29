<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })

async function onSubmit() {
  if (form.newPassword !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    const result = await auth.changePassword(form.oldPassword, form.newPassword)
    if (!result.ok) {
      ElMessage.error(result.message)
      return
    }
    ElMessage.success('密码已更新')
    router.push({ name: 'home' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="login-title">
        修改密码
      </h1>
      <p class="login-sub">
        首次登录需修改初始密码(BR-4 · 至少 8 位且含字母与数字)
      </p>
      <el-form
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="原密码">
          <el-input
            v-model="form.oldPassword"
            type="password"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          @click="onSubmit"
        >
          确认修改
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
.login-card { width: 380px; background: var(--panel); }
.login-title { margin: 0; text-align: center; color: var(--ink); }
.login-sub { margin: 4px 0 16px; text-align: center; color: var(--ink-2); font-size: 13px; }
.login-btn { width: 100%; }
</style>
