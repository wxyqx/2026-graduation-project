/**
 * 【这个文件是干什么的？】
 * 路由表 = 「网址 → 显示哪个页面」的对应关系，外加一个门卫（守卫）。
 *
 *   /login /register         全屏页，不用登录
 *   /positions 等            后台页，套在 AdminLayout（左菜单 + 顶栏）里面，必须登录
 *
 * 门卫规则（beforeEach）：
 *   没登录却想进后台页 → 送去 /login，并记住原来想去哪（登录后跳回去）
 *   已登录却访问登录页 → 直接送进后台
 */
import { createRouter, createWebHistory } from 'vue-router'

import { auth } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true, title: '登录' } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { public: true, title: '注册' } },
  {
    path: '/',
    component: () => import('../layouts/AdminLayout.vue'),
    redirect: '/positions',
    children: [
      { path: 'positions', name: 'positions', component: () => import('../views/PositionsView.vue'), meta: { title: '岗位管理' } },
      { path: 'candidates', name: 'candidates', component: () => import('../views/CandidatesView.vue'), meta: { title: '候选人管理' } },
      { path: 'applications', name: 'applications', component: () => import('../views/ApplicationsView.vue'), meta: { title: '投递列表' } },
      { path: 'applications/:id', name: 'application-detail', component: () => import('../views/ApplicationDetailView.vue'), meta: { title: '投递详情' } },
      { path: 'stats', name: 'stats', component: () => import('../views/StatsView.vue'), meta: { title: '汇总导出' } },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '系统设置' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }, // 乱输网址一律回首页
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !auth.isLoggedIn.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.public && auth.isLoggedIn.value) {
    return { name: 'positions' }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · ATS 招聘管理系统` : 'ATS 招聘管理系统'
})

export default router
