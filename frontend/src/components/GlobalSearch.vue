<script setup lang="ts">
import { useRouter } from 'vue-router'

import SearchBox from '@/components/SearchBox.vue'
import { useMarketStore } from '@/stores/market'

const router = useRouter()
const market = useMarketStore()

function onSelect(parcelNumber: string): void {
  void router.push({ name: 'parcel', params: { market: market.active, id: parcelNumber } })
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
