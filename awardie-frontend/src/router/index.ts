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
        { path: 'admin/awards/:id/edit', name: 'admin-award-edit', component: () => import('../views/AwardEditView.vue') },
        { path: 'admin/patents/:id/edit', name: 'admin-patent-edit', component: () => import('../views/PatentEditView.vue') },
        { path: 'admin/software/:id/edit', name: 'admin-software-edit', component: () => import('../views/SoftwareEditView.vue') },
        { path: 'admin/innovation/:id/edit', name: 'admin-innovation-edit', component: () => import('../views/InnovationEditView.vue') },
        { path: 'admin/achievements', name: 'admin-achievements', component: () => import('../views/AdminAchievementsView.vue') },
        { path: 'admin/competitions', name: 'admin-competitions', component: () => import('../views/AdminCompetitionsView.vue') },
        { path: 'admin/dashboard', name: 'admin-dashboard', component: () => import('../views/AdminDashboardView.vue') },
        // #29 侧边栏补全批次
        { path: 'admin/logs', name: 'admin-logs', component: () => import('../views/AdminLogsView.vue') },
        { path: 'admin/students', name: 'admin-students', component: () => import('../views/AdminStudentsView.vue') },
        { path: 'admin/teachers', name: 'admin-teachers', component: () => import('../views/AdminTeachersView.vue') },
        { path: 'admin/laboratories', name: 'admin-laboratories', component: () => import('../views/AdminLaboratoriesView.vue') },
        { path: 'admin/laboratories/:id', name: 'admin-lab-view', component: () => import('../views/LabDetailView.vue') },
        { path: 'admin/laboratories/:id/edit', name: 'admin-lab-edit', component: () => import('../views/LabEditView.vue') },
        { path: 'admin/laboratories/:id/downloads', name: 'admin-lab-downloads', component: () => import('../views/LabDownloadsView.vue') },
        { path: 'admin/templates', name: 'admin-templates', component: () => import('../views/AdminTemplatesView.vue') },
        { path: 'admin/data-analysis', name: 'admin-data-analysis', component: () => import('../views/AdminDataAnalysisView.vue') },
        { path: 'admin/data-export', name: 'admin-data-export', component: () => import('../views/AdminDataExportView.vue') },
        { path: 'admin/settings', name: 'admin-settings', component: () => import('../views/AdminSettingsView.vue') },
        { path: 'admin/import', name: 'admin-import', component: () => import('../views/AdminImportView.vue') },
        // Fix-B:审核/Chat 回 console 壳(admin 视角;同组件双注册,师生走 portal 路由)
        { path: 'admin/review', name: 'admin-review', component: () => import('../views/TeacherReviewView.vue') },
        { path: 'admin/review/:id', name: 'admin-review-view', component: () => import('../views/AdminReviewDetailView.vue') },
        { path: 'admin/competitions/:id', name: 'admin-competition-view', component: () => import('../views/AdminCompetitionDetailView.vue') },
        { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue'), meta: { roles: ['admin'] } },
        { path: 'coming-soon', name: 'coming-soon', component: () => import('../views/ComingSoonView.vue') },
      ],
    },
    {
      // 师生门户壳(Portal Shell,#35 对照 v1 user_base.html 顶部导航体系)
      path: '/portal',
      component: () => import('../layouts/PortalLayout.vue'),
      children: [
        { path: 'student/dashboard', name: 'student-dashboard', component: () => import('../views/StudentDashboardView.vue'), meta: { roles: ['student'] } },
        { path: 'student/achievements', name: 'student-achievements', component: () => import('../views/StudentAchievementsView.vue'), meta: { roles: ['student'] } },
        { path: 'submit', name: 'submit', component: () => import('../views/StudentSubmitView.vue'), meta: { roles: ['student', 'teacher'] } },
        { path: 'teacher/dashboard', name: 'teacher-dashboard', component: () => import('../views/TeacherDashboardView.vue'), meta: { roles: ['teacher'] } },
        { path: 'teacher/achievements', name: 'teacher-achievements', component: () => import('../views/TeacherAchievementsView.vue'), meta: { roles: ['teacher'] } },
        { path: 'teacher/export', name: 'teacher-export', component: () => import('../views/TeacherExportView.vue'), meta: { roles: ['teacher'] } },
        { path: 'teacher/review', name: 'teacher-review', component: () => import('../views/TeacherReviewView.vue'), meta: { roles: ['teacher', 'admin'] } },
        { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
        { path: 'chat', name: 'portal-chat', component: () => import('../views/ChatView.vue') },
      ],
    },
    // 旧路径重定向:师生落 portal,admin 视角的审核落 console(按请求无法判角色,守卫二次校正)
    { path: '/student/dashboard', redirect: '/portal/student/dashboard' },
    { path: '/student/achievements', redirect: '/portal/student/achievements' },
    { path: '/submit', redirect: '/portal/submit' },
    { path: '/teacher/dashboard', redirect: '/portal/teacher/dashboard' },
    { path: '/teacher/achievements', redirect: '/portal/teacher/achievements' },
    { path: '/teacher/export', redirect: '/portal/teacher/export' },
    { path: '/teacher/review', redirect: '/portal/teacher/review' },
    { path: '/profile', redirect: '/portal/profile' },
    { path: '/chat', redirect: '/portal/chat' },
  ],
})

// 守卫:未登录拦截;BR-4 首登强制改密;登录后按角色落门户;portal 角色守卫(#Fix-B)
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
    // 登录后按角色落门户(#35/#36):学生→学生仪表板,教师→教师仪表板,admin→控制台工作台
    const role = auth.user?.role
    if (role === 'student') {
      return '/portal/student/dashboard'
    }
    if (role === 'teacher') {
      return '/portal/teacher/dashboard'
    }
    return { name: 'home' }
  }
  if (auth.isLoggedIn && auth.needsPasswordChange && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
  // 师生访问 console 根 → 各自门户仪表板(admin 留控制台)
  if (to.path === '/' && auth.user?.role === 'student') {
    return '/portal/student/dashboard'
  }
  if (to.path === '/' && auth.user?.role === 'teacher') {
    return '/portal/teacher/dashboard'
  }
  // AI 助手对所有角色可用:师生访问 console 版 /chat 时引导回 portal 版
  if (to.path === '/chat' && auth.user?.role !== 'admin') {
    return '/portal/chat'
  }
  // portal 角色守卫(meta.roles 声明;越权重定向本角色首页)
  if (to.meta?.roles && auth.user) {
    const allowed = to.meta.roles as string[]
    const role = auth.user.role
    if (!allowed.includes(role)) {
      if (role === 'student') {
        return '/portal/student/dashboard'
      }
      if (role === 'teacher') {
        return '/portal/teacher/dashboard'
      }
      return { name: 'home' }
    }
  }
})

export default router
