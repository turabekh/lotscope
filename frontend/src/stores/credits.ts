import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/lib/api'

export const useCreditsStore = defineStore('credits', () => {
  const balance = ref<number | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  async function refresh(): Promise<void> {
    loading.value = true
    try {
      balance.value = (await api.getCredits()).balance
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (!loaded.value && !loading.value) await refresh()
  }

  function set(next: number): void {
    balance.value = next
    loaded.value = true
  }

  return { balance, loaded, loading, refresh, ensureLoaded, set }
})
