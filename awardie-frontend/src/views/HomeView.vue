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
    <h2>v2 控制台</h2>
    <p v-if="auth.user">
      当前用户:<b>{{ auth.user.name }}</b> · 角色:{{ auth.user.role }} · 学工号:{{ auth.user.id }}
    </p>

    <h3>业务入口</h3>
    <ul class="links">
      <li>
        <router-link to="/submit">
          提交奖状
        </router-link>(学生)
      </li>
      <li>
        <router-link to="/teacher/review">
          教师审核台
        </router-link>(教师/管理员)
      </li>
      <li>
        <router-link to="/profile">
          个人资料
        </router-link>
      </li>
    </ul>

    <template v-if="auth.user?.role === 'admin'">
      <h3>管理端(admin)</h3>
      <ul class="links">
        <li>
          <router-link to="/admin/awards">
            成果管理
          </router-link>
        </li>
        <li>
          <router-link to="/admin/competitions">
            竞赛管理
          </router-link>
        </li>
        <li>
          <router-link to="/admin/dashboard">
            数据看板
          </router-link>
        </li>
      </ul>
    </template>

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
h2, h3 { color: var(--ink); margin: 12px 0; }
.links { list-style: none; padding: 0; }
.links li { padding: 4px 0; }
.links a { color: var(--brand); }
</style>
