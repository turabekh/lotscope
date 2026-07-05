import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import type { MarketInfo } from '@/lib/types'

export const MARKETS = ['philadelphia'] as const
export type Market = (typeof MARKETS)[number]
export const DEFAULT_MARKET: Market = 'philadelphia'

export const MARKET_LABELS: Record<Market, string> = {
  philadelphia: 'Philadelphia',
}

const STORAGE_KEY = 'lotscope.market'

export function isKnownMarket(value: unknown): value is Market {
  return typeof value === 'string' && (MARKETS as readonly string[]).includes(value)
}

export const useMarketStore = defineStore('market', () => {
  const stored = localStorage.getItem(STORAGE_KEY)
  const active = ref<Market>(isKnownMarket(stored) ? stored : DEFAULT_MARKET)
  const infos = ref<MarketInfo[]>([])

  const activeInfo = computed<MarketInfo | null>(
    () => infos.value.find((m) => m.url_slug === active.value) ?? null,
  )

  function set(next: Market): void {
    active.value = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  async function load(): Promise<void> {
    if (infos.value.length === 0) {
      infos.value = await api.getMarkets()
    }
  }

  return { active, infos, activeInfo, set, load }
})
