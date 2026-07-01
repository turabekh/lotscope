import {
  createRouter,
  createWebHistory,
  type NavigationGuard,
  type RouteRecordRaw,
} from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { DEFAULT_MARKET, isKnownMarket, useMarketStore } from '@/stores/market'

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
    path: '/:market',
    name: 'market-root',
    redirect: (to) => ({ name: 'home', params: { market: to.params.market } }),
    meta: { requiresAuth: true },
  },
  {
    path: '/:market/home',
    name: 'home',
    redirect: (to) => ({ name: 'explore', params: { market: to.params.market } }),
    meta: { requiresAuth: true },
  },
  {
    path: '/:market/explore',
    name: 'explore',
    component: () => import('@/pages/ExplorePage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/:market/leads',
    name: 'leads',
    component: () => import('@/pages/LeadsPage.vue'),
    meta: { requiresAuth: true, title: 'Motivated-seller leads' },
  },
  {
    path: '/:market/pipeline',
    name: 'pipeline',
    component: () => import('@/pages/PipelinePage.vue'),
    meta: { requiresAuth: true, title: 'Deal pipeline' },
  },
  {
    path: '/:market/watchlist',
    name: 'watchlist',
    component: () => import('@/pages/WatchlistPage.vue'),
    meta: { requiresAuth: true, title: 'My watchlist' },
  },
  {
    path: '/:market/compare',
    name: 'compare',
    component: () => import('@/pages/ComparePage.vue'),
    meta: { requiresAuth: true, title: 'Compare parcels' },
  },
  {
    path: '/:market/saved-searches',
    name: 'saved-searches',
    component: () => import('@/pages/SavedSearchesPage.vue'),
    meta: { requiresAuth: true, title: 'Saved searches' },
  },
]

export const marketGuard: NavigationGuard = (to) => {
  const auth = useAuthStore()
  const market = useMarketStore()

  const marketParam = to.params.market
  if (marketParam !== undefined && marketParam !== '') {
    if (!isKnownMarket(marketParam)) {
      return {
        name: (to.name as string | undefined) ?? 'home',
        params: { ...to.params, market: DEFAULT_MARKET },
        query: to.query,
        hash: to.hash,
      }
    }
    market.set(marketParam)
  }

  if (to.meta.requiresAuth && auth.token === null) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.token !== null) {
    return { name: 'home', params: { market: market.active } }
  }
  if (to.meta.requiresAdmin && auth.user !== null && auth.user.role !== 'admin') {
    return { name: 'home', params: { market: market.active } }
  }
  if (to.name === 'landing' && auth.token !== null) {
    return { name: 'home', params: { market: market.active } }
  }
  return true
}

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(marketGuard)
