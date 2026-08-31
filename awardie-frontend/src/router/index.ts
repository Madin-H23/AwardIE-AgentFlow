import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory('/v2/'),
  routes: [
    // 登录/改密不带 Shell(#25)
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    { path: '/change-password', name: 'change-password', component: () => import('../views/ChangePasswordView.vue') },
    {
      // admin 控制台壳(Console Shell,对照 v1 base_console 侧边栏体系)
      path: '/',
      component: () => import('../layouts/ConsoleLayout.vue'),
      children: [
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
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
        { path: 'admin/import', name: 'admin-import', component: () => import('../views/AdminImportView.vue') },
        { path: 'coming-soon', name: 'coming-soon', component: () => import('../views/ComingSoonView.vue') },
      ],
    },
    {
      // 师生门户壳(Portal Shell,#35 对照 v1 user_base.html 顶部导航体系)
      path: '/portal',
      component: () => import('../layouts/PortalLayout.vue'),
      children: [
        { path: 'student/dashboard', name: 'student-dashboard', component: () => import('../views/StudentDashboardView.vue') },
        { path: 'student/achievements', name: 'student-achievements', component: () => import('../views/StudentAchievementsView.vue') },
        { path: 'submit', name: 'submit', component: () => import('../views/StudentSubmitView.vue') },
        { path: 'teacher/review', name: 'teacher-review', component: () => import('../views/TeacherReviewView.vue') },
        { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
        { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue') },
      ],
    },
    // 旧路径重定向到门户壳(路径本体不变,E2E/书签兼容)
    { path: '/student/dashboard', redirect: '/portal/student/dashboard' },
    { path: '/student/achievements', redirect: '/portal/student/achievements' },
    { path: '/submit', redirect: '/portal/submit' },
    { path: '/teacher/review', redirect: '/portal/teacher/review' },
    { path: '/profile', redirect: '/portal/profile' },
    { path: '/chat', redirect: '/portal/chat' },
  ],
})

// 守卫:未登录拦截;BR-4 首登强制改密;登录后根路径按角色落对应门户(#35)
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureLoaded()
  if (to.name !== 'login' && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    if (auth.needsPasswordChange) {
      return { name: 'change-password' }
    }
    // 学生落门户仪表板(#35);教师仪表板属 Goal D,暂落工作台
    return auth.user?.role === 'student' ? '/portal/student/dashboard' : { name: 'home' }
  }
  if (auth.isLoggedIn && auth.needsPasswordChange && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
  // 学生访问 console 根 → 门户仪表板(admin/教师不受影响)
  if (to.path === '/' && auth.user?.role === 'student') {
    return '/portal/student/dashboard'
  }
})

export default router
