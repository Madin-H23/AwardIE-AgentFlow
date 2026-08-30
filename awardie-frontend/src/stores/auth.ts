import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiJson } from '../composables/useCsrf'

export interface UserInfo {
  id: number
  name: string
  role: 'student' | 'teacher' | 'admin'
  needsPasswordChange: boolean
}

/**
 * 认证状态(会话制):登录态经 /api/v2/auth/* 与 Spring Security JSESSIONID 绑定。
 * 刷新后由 /me 恢复(路由守卫调用 ensureLoaded)。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const loaded = ref(false)

  const isLoggedIn = computed(() => user.value !== null)
  const needsPasswordChange = computed(() => user.value?.needsPasswordChange ?? false)

  async function ensureLoaded() {
    if (loaded.value) return
    try {
      const resp = await fetch('/api/v2/auth/me', { credentials: 'include' })
      const body = await resp.json()
      user.value = body.code === 0 ? (body.data as UserInfo) : null
    } catch {
      user.value = null
    }
    loaded.value = true
  }

  async function login(account: string, password: string): Promise<{ ok: boolean; message: string }> {
    const body = await apiJson('POST', '/api/v2/auth/login', { account, password })
    if (body.code === 0) {
      user.value = body.data as UserInfo
      loaded.value = true
      return { ok: true, message: body.message }
    }
    return { ok: false, message: body.message }
  }

  async function changePassword(oldPassword: string, newPassword: string): Promise<{ ok: boolean; message: string }> {
    const body = await apiJson('POST', '/api/v2/auth/password', { oldPassword, newPassword })
    if (body.code === 0 && user.value) {
      user.value.needsPasswordChange = false
    }
    return { ok: body.code === 0, message: body.message }
  }

  async function logout() {
    await apiJson('POST', '/api/v2/auth/logout')
    user.value = null
    loaded.value = false
  }

  return { user, isLoggedIn, needsPasswordChange, ensureLoaded, login, changePassword, logout }
})
