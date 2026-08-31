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
        // #29 侧边栏补全批次
        { path: 'admin/logs', name: 'admin-logs', component: () => import('../views/AdminLogsView.vue') },
        { path: 'admin/students', name: 'admin-students', component: () => import('../views/AdminStudentsView.vue') },
        { path: 'admin/teachers', name: 'admin-teachers', component: () => import('../views/AdminTeachersView.vue') },
        { path: 'admin/laboratories', name: 'admin-laboratories', component: () => import('../views/AdminLaboratoriesView.vue') },
        { path: 'admin/templates', name: 'admin-templates', component: () => import('../views/AdminTemplatesView.vue') },
        { path: 'admin/data-analysis', name: 'admin-data-analysis', component: () => import('../views/AdminDataAnalysisView.vue') },
        { path: 'admin/data-export', name: 'admin-data-export', component: () => import('../views/AdminDataExportView.vue') },
        { path: 'admin/settings', name: 'admin-settings', component: () => import('../views/AdminSettingsView.vue') },
        { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue') },
        { path: 'admin/import', name: 'admin-import', component: () => import('../views/AdminImportView.vue') },
        { path: 'coming-soon', name: 'coming-soon', component: () => import('../views/ComingSoonView.vue') },
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
