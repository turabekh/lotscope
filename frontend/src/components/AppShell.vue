<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AppSidebar from '@/components/AppSidebar.vue'
import AppTopBar from '@/components/AppTopBar.vue'
import VerifyEmailBanner from '@/components/VerifyEmailBanner.vue'

const $q = useQuasar()
const route = useRoute()

const isMobile = computed(() => $q.screen.lt.md)
const collapsed = ref(false)
const drawerOpen = ref(!isMobile.value)

const hideFooter = computed(() => route.name === 'parcel')
const showFooter = computed(() => isMobile.value && !hideFooter.value)
const footerVar = computed(() => (showFooter.value ? '56px' : '0px'))

watch(isMobile, (mobile) => {
  drawerOpen.value = !mobile
})
</script>

<template>
  <q-layout view="lHh Lpr lFf" class="shell" :style="{ '--lot-footer-h': footerVar }">
    <q-drawer
      v-model="drawerOpen"
      show-if-above
      side="left"
      bordered
      :width="collapsed && !isMobile ? 64 : 220"
      :breakpoint="1023"
    >
      <AppSidebar
        :collapsed="collapsed && !isMobile"
        :mobile="isMobile"
        @toggle="collapsed = !collapsed"
        @navigate="isMobile && (drawerOpen = false)"
      />
    </q-drawer>

    <AppTopBar />

    <q-page-container>
      <VerifyEmailBanner />
      <slot />
    </q-page-container>

    <q-footer v-if="showFooter" class="mobile-footer"> </q-footer>
  </q-layout>
</template>

<style scoped>
.shell {
  background: var(--lot-bg);
}
.mobile-footer {
  background: var(--lot-surface);
  color: var(--lot-ink);
}
</style>
