import { createRouter, createWebHistory } from 'vue-router';
import MapPage from '@/pages/MapPage.vue';
const routes = [{ path: '/', name: 'map', component: MapPage }];
export const router = createRouter({
    history: createWebHistory(),
    routes,
});
