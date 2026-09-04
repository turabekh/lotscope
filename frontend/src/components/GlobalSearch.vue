<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import SearchBox from '@/components/SearchBox.vue'

const router = useRouter()
const $q = useQuasar()

const compact = computed(() => $q.screen.lt.sm)
const open = ref(false)

function onSelect(parcelNumber: string): void {
  open.value = false
  void router.push({ name: 'parcel', params: { id: parcelNumber } })
}
</script>

<template>
  <div v-if="compact" class="global-search-compact">
    <q-btn
      flat
      dense
      round
      icon="search"
      aria-label="Search parcels"
      data-test="global-search-open"
      @click="open = true"
    />
    <q-dialog v-model="open" position="top">
      <q-card class="search-sheet" data-test="global-search-dialog">
        <q-card-section class="q-pb-none">
          <SearchBox autofocus @select="onSelect" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat no-caps label="Cancel" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>

  <div v-else class="global-search">
    <SearchBox @select="onSelect" />
  </div>
</template>

<style scoped>
.global-search {
  flex: 1;
  max-width: 420px;
  min-width: 0;
}
.global-search-compact {
  flex: none;
}
.search-sheet {
  width: 96vw;
  max-width: 560px;
  border-radius: 14px;
}
</style>
