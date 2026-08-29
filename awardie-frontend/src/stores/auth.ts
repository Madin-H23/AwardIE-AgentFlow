import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * 认证状态占位:P0 骨架阶段无后端,dev 登录仅置本地状态。
 * T4(登录端到端)接线 Spring Security 后替换为本真实现。
 */
export const useAuthStore = defineStore('auth', () => {
  const username = ref<string | null>(null)
  const role = ref<'student' | 'teacher' | 'admin' | null>(null)

  const isLoggedIn = computed(() => username.value !== null)

  function devLogin(name: string, r: 'student' | 'teacher' | 'admin') {
    username.value = name
    role.value = r
  }

  function logout() {
    username.value = null
    role.value = null
  }

  return { username, role, isLoggedIn, devLogin, logout }
})
