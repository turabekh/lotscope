import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/pages/LandingPage.vue') },
  { path: '/app', name: 'map', component: () => import('@/pages/MapPage.vue'), meta: { requiresAuth: true } },
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
    meta: { requiresAuth: true },
  },
  {
    path: '/leads',
    name: 'leads',
    component: () => import('@/pages/LeadsPage.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/watchlist',
    name: 'watchlist',
    component: () => import('@/pages/WatchlistPage.vue'),
    meta: { requiresAuth: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && auth.token === null) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.token !== null) {
    return { name: 'map' }
  }
  return true
})
