import {
  createRouter,
  createWebHistory,
  type NavigationGuard,
  type RouteRecordRaw,
} from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
    guestOnly?: boolean
    title?: string
  }
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'analyst',
    component: () => import('@/pages/AnalystPage.vue'),
    meta: { requiresAuth: true, title: 'Analyst' },
  },
  {
    path: '/lot/:parcelNumber',
    name: 'lot',
    component: () => import('@/pages/LotPage.vue'),
    meta: { requiresAuth: true, title: 'Lot' },
  },
  {
    path: '/deals',
    name: 'deals',
    component: () => import('@/pages/DealsPage.vue'),
    meta: { requiresAuth: true, title: 'Deals' },
  },
  {
    path: '/packets',
    name: 'packets',
    component: () => import('@/pages/PacketsPage.vue'),
    meta: { requiresAuth: true, title: 'Sale packets' },
  },
  {
    path: '/account',
    name: 'account',
    component: () => import('@/pages/AccountPage.vue'),
    meta: { requiresAuth: true, title: 'Account' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/pages/AdminPage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Admin console' },
  },
  {
    path: '/welcome',
    name: 'welcome',
    component: () => import('@/pages/WelcomePage.vue'),
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/AuthPage.vue'),
    props: { mode: 'login' },
    meta: { guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/AuthPage.vue'),
    props: { mode: 'register' },
    meta: { guestOnly: true },
  },
  {
    path: '/verify',
    name: 'verify',
    component: () => import('@/pages/VerifyPage.vue'),
  },
  {
    path: '/legal/:slug?',
    name: 'legal',
    component: () => import('@/pages/LegalPage.vue'),
  },
  // Everything Phase 3 removed. A saved link should land somewhere honest rather than on
  // a blank 404, and the Analyst is where all of it now happens.
  { path: '/:pathMatch(.*)*', redirect: { name: 'analyst' } },
]

export const authGuard: NavigationGuard = async (to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.hasLiveToken) {
    auth.endSession()
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.hasLiveToken) {
    return { name: 'analyst' }
  }
  if (to.meta.requiresAdmin) {
    await auth.ensureRestored()
    if (auth.user === null || auth.user.role !== 'admin') {
      return { name: 'analyst' }
    }
  }
  return true
}

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(authGuard)
