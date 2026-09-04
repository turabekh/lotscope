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
  { path: '/', name: 'landing', component: () => import('@/pages/LandingPage.vue') },
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
    path: '/admin/ops',
    name: 'ops',
    component: () => import('@/pages/OpsPage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Fleet health' },
  },
  {
    path: '/admin/ops/market',
    name: 'ops-market',
    component: () => import('@/pages/MarketHealthPage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Market health' },
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('@/pages/HomePage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/explore',
    name: 'explore',
    component: () => import('@/pages/ExplorePage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/leads',
    name: 'leads',
    component: () => import('@/pages/LeadsPage.vue'),
    meta: { requiresAuth: true, title: 'Motivated-seller leads' },
  },
  {
    path: '/feed',
    name: 'feed',
    component: () => import('@/pages/FeedPage.vue'),
    meta: { requiresAuth: true, title: 'Deal feed' },
  },
  {
    path: '/sheriff-sales',
    name: 'sheriff-sales',
    component: () => import('@/pages/SheriffSalesPage.vue'),
    meta: { requiresAuth: true, title: 'Sheriff sales' },
  },
  {
    path: '/buyers',
    name: 'buyers',
    component: () => import('@/pages/BuyersPage.vue'),
    meta: { requiresAuth: true, title: 'Cash buyers' },
  },
  {
    path: '/buyers/:buyerKey',
    name: 'buyer-profile',
    component: () => import('@/pages/BuyerProfilePage.vue'),
    meta: { requiresAuth: true, title: 'Buyer profile' },
  },
  {
    path: '/top-plays',
    name: 'top-plays',
    component: () => import('@/pages/TopPlaysPage.vue'),
    meta: { requiresAuth: true, title: 'Top plays' },
  },
  {
    path: '/market',
    name: 'market',
    component: () => import('@/pages/MarketPage.vue'),
    meta: { requiresAuth: true, title: 'Market' },
  },
  {
    path: '/pipeline',
    name: 'pipeline',
    component: () => import('@/pages/PipelinePage.vue'),
    meta: { requiresAuth: true, title: 'Deal pipeline' },
  },
  {
    path: '/lists',
    name: 'lists',
    component: () => import('@/pages/ListsPage.vue'),
    meta: { requiresAuth: true, title: 'Lists' },
  },
  {
    path: '/watchlist',
    name: 'watchlist',
    redirect: (to) => ({
      name: 'lists',
      query: { ...to.query, tab: 'lots' },
    }),
    meta: { requiresAuth: true },
  },
  {
    path: '/compare',
    name: 'compare',
    redirect: (to) => ({ name: 'explore', query: to.query }),
    meta: { requiresAuth: true },
  },
  {
    path: '/saved-searches',
    name: 'saved-searches',
    redirect: (to) => ({
      name: 'lists',
      query: { ...to.query, tab: 'searches' },
    }),
    meta: { requiresAuth: true },
  },
  {
    path: '/legal/:slug?',
    name: 'legal',
    component: () => import('@/pages/LegalPage.vue'),
  },
  {
    path: '/parcel/:id',
    name: 'parcel',
    component: () => import('@/pages/ParcelDossierPage.vue'),
    meta: { requiresAuth: true },
  },
]

export const authGuard: NavigationGuard = async (to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.hasLiveToken) {
    auth.endSession()
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.hasLiveToken) {
    return { name: 'home' }
  }
  if (to.meta.requiresAdmin) {
    await auth.ensureRestored()
    if (auth.user === null || auth.user.role !== 'admin') {
      return { name: 'home' }
    }
  }
  if (to.name === 'landing' && auth.hasLiveToken) {
    return { name: 'home' }
  }
  return true
}

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(authGuard)
