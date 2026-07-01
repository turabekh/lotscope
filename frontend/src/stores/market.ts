import { defineStore } from 'pinia'
import { ref } from 'vue'

export const MARKETS = ['philadelphia'] as const
export type Market = (typeof MARKETS)[number]
export const DEFAULT_MARKET: Market = 'philadelphia'

const STORAGE_KEY = 'lotscope.market'

export function isKnownMarket(value: unknown): value is Market {
  return typeof value === 'string' && (MARKETS as readonly string[]).includes(value)
}

export const useMarketStore = defineStore('market', () => {
  const stored = localStorage.getItem(STORAGE_KEY)
  const active = ref<Market>(isKnownMarket(stored) ? stored : DEFAULT_MARKET)

  function set(next: Market): void {
    active.value = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  return { active, set }
})
