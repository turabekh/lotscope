<script setup lang="ts">
import { ref } from 'vue'

import AppSidebar from '@/components/AppSidebar.vue'
import AppTopBar from '@/components/AppTopBar.vue'
import CompareTray from '@/components/CompareTray.vue'

const open = ref(true)
const collapsed = ref(false)
</script>

<template>
  <q-layout view="lHh Lpr lFf" class="shell">
    <q-drawer v-model="open" show-if-above side="left" bordered :width="collapsed ? 64 : 220">
      <AppSidebar :collapsed="collapsed" @toggle="collapsed = !collapsed" />
    </q-drawer>

    <AppTopBar />

    <q-page-container>
      <slot />
    </q-page-container>

    <CompareTray />
  </q-layout>
</template>

<style scoped>
.shell {
  background: var(--lot-bg);
}
</style>
