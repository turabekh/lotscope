import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import MapPage from '@/pages/MapPage.vue'

const routes: RouteRecordRaw[] = [{ path: '/', name: 'map', component: MapPage }]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
