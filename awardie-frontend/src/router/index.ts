import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory('/v2/'),
  routes: [
    // 登录/改密不带 Console Shell(#25)
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    { path: '/change-password', name: 'change-password', component: () => import('../views/ChangePasswordView.vue') },
    {
      path: '/',
      component: () => import('../layouts/ConsoleLayout.vue'),
      children: [
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
        { path: 'submit', name: 'submit', component: () => import('../views/StudentSubmitView.vue') },
        { path: 'teacher/review', name: 'teacher-review', component: () => import('../views/TeacherReviewView.vue') },
        { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
        { path: 'admin/awards', name: 'admin-awards', component: () => import('../views/AdminAwardsView.vue') },
        { path: 'admin/competitions', name: 'admin-competitions', component: () => import('../views/AdminCompetitionsView.vue') },
        { path: 'admin/dashboard', name: 'admin-dashboard', component: () => import('../views/AdminDashboardView.vue') },
      ],
    },
  ],
})

// 守卫:未登录拦截;BR-4 首登强制改密(needs_password_change)
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureLoaded()
  if (to.name !== 'login' && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: auth.needsPasswordChange ? 'change-password' : 'home' }
  }
  if (auth.isLoggedIn && auth.needsPasswordChange && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
})

export default router
