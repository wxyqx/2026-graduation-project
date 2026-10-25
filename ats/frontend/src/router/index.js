/**
 * 【路由表】—— 管理端（HR）与候选人端两套入口
 *
 *   /login /register /positions ...   管理端（现有），套 AdminLayout
 *   /portal/login                     候选人登录（全屏）
 *   /portal/**                        候选人端，套 PortalLayout（移动优先）
 *
 * 门卫规则：
 *   · 候选人页面只认候选人 token（ats_portal_token）
 *   · 管理页面只认 HR token（ats_token）
 *   · 两套 token 分开存，同一浏览器可以同时开两个端联调
 */
import { createRouter, createWebHistory } from 'vue-router'

import { auth } from '../stores/auth'
import { portalAuth } from '../stores/portalAuth'
import { techAuth } from '../stores/techAuth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/UnifiedLoginView.vue'),
    meta: { public: true, title: '登录', loginRole: 'hr' },
  },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { public: true, title: '注册' } },

  // ---------------- 候选人端 ----------------
  {
    path: '/portal/login',
    name: 'portal-login',
    component: () => import('../views/UnifiedLoginView.vue'),
    meta: { public: true, portal: true, title: '候选人登录', loginRole: 'candidate' },
  },
  {
    path: '/portal',
    component: () => import('../layouts/PortalLayout.vue'),
    meta: { portal: true },
    redirect: { name: 'portal-positions' },
    children: [
      {
        path: 'positions',
        name: 'portal-positions',
        component: () => import('../views/portal/PortalPositionsView.vue'),
        meta: { portal: true, title: '在招岗位' },
      },
      {
        path: 'positions/:id',
        name: 'portal-position-detail',
        component: () => import('../views/portal/PortalPositionDetailView.vue'),
        meta: { portal: true, title: '岗位详情' },
      },
      {
        path: 'applications',
        name: 'portal-applications',
        component: () => import('../views/portal/PortalApplicationsView.vue'),
        meta: { portal: true, title: '我的投递', wide: true },
      },
      {
        path: 'applications/:id',
        name: 'portal-application-detail',
        component: () => import('../views/portal/PortalApplicationDetailView.vue'),
        meta: { portal: true, title: '投递详情' },
      },
      {
        path: 'files',
        name: 'portal-files',
        component: () => import('../views/portal/PortalFilesView.vue'),
        meta: { portal: true, title: '我的简历/附件' },
      },
      {
        path: 'forms',
        name: 'portal-forms-center',
        component: () => import('../views/portal/PortalFormsCenterView.vue'),
        meta: { portal: true, title: '我的表单' },
      },
      {
        path: 'forms/:templateId',
        name: 'portal-form',
        component: () => import('../views/portal/PortalFormView.vue'),
        meta: { portal: true, title: '填写表单', wide: true },
      },
      {
        path: 'profile',
        name: 'portal-profile',
        component: () => import('../views/portal/PortalProfileView.vue'),
        meta: { portal: true, title: '我的资料' },
      },
    ],
  },

  // ---------------- 技术管理端 ----------------
  {
    path: '/tech/login',
    name: 'tech-login',
    component: () => import('../views/UnifiedLoginView.vue'),
    meta: { public: true, tech: true, title: '技术管理登录', loginRole: 'tech' },
  },
  {
    path: '/tech',
    component: () => import('../layouts/TechLayout.vue'),
    meta: { tech: true },
    redirect: { name: 'tech-overview' },
    children: [
      {
        path: '',
        name: 'tech-overview',
        component: () => import('../views/tech/TechOverviewView.vue'),
        meta: { tech: true, title: '运行概览' },
      },
      {
        path: 'accounts',
        name: 'tech-accounts',
        component: () => import('../views/tech/TechAccountsView.vue'),
        meta: { tech: true, title: '账号管理' },
      },
      {
        path: 'config',
        name: 'tech-config',
        component: () => import('../views/tech/TechConfigView.vue'),
        meta: { tech: true, title: '系统配置' },
      },
      {
        path: 'candidate-owners',
        name: 'tech-candidate-owners',
        component: () => import('../views/tech/TechCandidateOwnersView.vue'),
        meta: { tech: true, title: '候选人负责人' },
      },
      {
        path: 'stage-owners',
        name: 'tech-stage-owners',
        component: () => import('../views/tech/TechStageOwnersView.vue'),
        meta: { tech: true, title: '关卡负责人' },
      },
      {
        path: 'logs',
        name: 'tech-logs',
        component: () => import('../views/tech/TechLogsView.vue'),
        meta: { tech: true, title: '操作日志' },
      },
      {
        path: 'backup',
        name: 'tech-backup',
        component: () => import('../views/tech/TechBackupView.vue'),
        meta: { tech: true, title: '备份导出' },
      },
    ],
  },

  // ---------------- 管理端（HR） ----------------
  {
    path: '/',
    component: () => import('../layouts/AdminLayout.vue'),
    redirect: '/positions',
    children: [
      { path: 'positions', name: 'positions', component: () => import('../views/PositionsView.vue'), meta: { title: '岗位管理' } },
      { path: 'candidates', name: 'candidates', component: () => import('../views/CandidatesView.vue'), meta: { title: '候选人管理' } },
      { path: 'form-templates', name: 'form-templates', component: () => import('../views/FormTemplatesView.vue'), meta: { title: '表单模板' } },
      { path: 'applications', name: 'applications', component: () => import('../views/ApplicationsView.vue'), meta: { title: '投递列表' } },
      { path: 'applications/:id', name: 'application-detail', component: () => import('../views/ApplicationDetailView.vue'), meta: { title: '投递详情' } },
      { path: 'interview', name: 'interview', component: () => import('../views/InterviewView.vue'), meta: { title: '面试评价' } },
      { path: 'stats', name: 'stats', component: () => import('../views/StatsView.vue'), meta: { title: '汇总导出' } },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '系统设置' } },
    ],
  },

  {
    path: '/:pathMatch(.*)*',
    redirect: (to) =>
      to.path.startsWith('/portal') ? '/portal' : to.path.startsWith('/tech') ? '/tech' : '/',
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const isTech = to.matched.some((r) => r.meta.tech)
  if (isTech) {
    if (to.meta.public) {
      if (techAuth.isLoggedIn.value) return { name: 'tech-overview' }
      return
    }
    if (!techAuth.isLoggedIn.value) {
      return { name: 'tech-login', query: { redirect: to.fullPath } }
    }
    return
  }

  const isPortal = to.matched.some((r) => r.meta.portal)

  if (isPortal) {
    if (to.meta.public) {
      if (portalAuth.isLoggedIn.value) return { name: 'portal-positions' }
      return
    }
    if (!portalAuth.isLoggedIn.value) {
      return { name: 'portal-login', query: { redirect: to.fullPath } }
    }
    return
  }

  if (!to.meta.public && !auth.isLoggedIn.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.public && auth.isLoggedIn.value) {
    return { name: 'positions' }
  }
})

router.afterEach((to) => {
  const base = to.meta.title ? `${to.meta.title} · ATS 招聘` : 'ATS 招聘'
  if (to.meta.tech) document.title = `${base}（技术管理）`
  else if (to.meta.portal) document.title = `${base}（候选人）`
  else document.title = base
})

export default router
