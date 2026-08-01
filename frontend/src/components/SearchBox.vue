<script setup lang="ts">
import { ref } from 'vue'

import { api } from '@/lib/api'
import type { ParcelSearchResult } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

const props = withDefaults(defineProps<{ autofocus?: boolean }>(), { autofocus: false })
const emit = defineEmits<{ select: [parcelNumber: string] }>()

const market = useMarketStore()

const query = ref('')
const results = ref<ParcelSearchResult[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

function onInput(value: string | number | null): void {
  query.value = value == null ? '' : String(value)
  if (timer !== undefined) clearTimeout(timer)
  timer = setTimeout(() => {
    void runSearch()
  }, 250)
}

async function runSearch(): Promise<void> {
  const term = query.value.trim()
  if (term === '') {
    results.value = []
    return
  }
  loading.value = true
  try {
    const response = await api.search(term, market.active)
    results.value = response.results
  } finally {
    loading.value = false
  }
}

function choose(parcelNumber: string): void {
  results.value = []
  query.value = ''
  emit('select', parcelNumber)
}
</script>

<template>
  <div>
    <q-input
      :model-value="query"
      :loading="loading"
      :autofocus="props.autofocus"
      dense
      outlined
      placeholder="Search address, owner, or parcel #"
      @update:model-value="onInput"
    >
      <template #prepend><q-icon name="search" /></template>
    </q-input>
    <q-list v-if="results.length" bordered class="q-mt-xs results-list">
      <q-item
        v-for="item in results"
        :key="item.parcel_number"
        v-ripple
        clickable
        @click="choose(item.parcel_number)"
      >
        <q-item-section>
          <q-item-label>{{ item.address ?? item.parcel_number }}</q-item-label>
          <q-item-label caption>{{ item.owner ?? '—' }} · {{ item.parcel_number }}</q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  </div>
</template>

<style scoped>
.results-list {
  background: var(--lot-surface);
}
</style>
