<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ account: '', password: '' })

async function onSubmit() {
  if (!form.account || !form.password) {
    ElMessage.warning('请输入账号与密码')
    return
  }
  loading.value = true
  try {
    const result = await auth.login(form.account, form.password)
    if (!result.ok) {
      ElMessage.error(result.message)
      return
    }
    ElMessage.success('登录成功')
    // BR-4:首登强制改密
    if (auth.needsPasswordChange) {
      router.push({ name: 'change-password' })
      return
    }
    // 登录后按角色落对应门户(#35/#36):学生/教师→门户仪表板,admin→控制台工作台
    const role = auth.user?.role
    if (role === 'student') {
      router.push('/portal/student/dashboard')
    } else if (role === 'teacher') {
      router.push('/portal/teacher/dashboard')
    } else {
      router.push({ name: 'home' })
    }
  } finally {
    loading.value = false
  }
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
