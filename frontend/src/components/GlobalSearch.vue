<script setup lang="ts">
import { useRouter } from 'vue-router'

import SearchBox from '@/components/SearchBox.vue'
import { useMarketStore } from '@/stores/market'
import { useParcelStore } from '@/stores/parcel'

const router = useRouter()
const market = useMarketStore()
const parcelStore = useParcelStore()

function onSelect(parcelNumber: string): void {
  void parcelStore.select(parcelNumber)
  void router.push({ name: 'explore', params: { market: market.active } })
}
</script>

<template>
  <div class="global-search">
    <SearchBox @select="onSelect" />
  </div>
</template>

<style scoped>
.global-search {
  flex: 1;
  max-width: 420px;
}
</style>
