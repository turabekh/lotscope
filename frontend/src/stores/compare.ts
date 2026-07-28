import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

const STORAGE_KEY = 'lotscope.compare'
export const MAX_COMPARE = 4

function loadInitial(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((value): value is string => typeof value === 'string')
      .slice(0, MAX_COMPARE)
  } catch {
    return []
  }
}

export const useCompareStore = defineStore('compare', () => {
  const parcelNumbers = ref<string[]>(loadInitial())

  const count = computed(() => parcelNumbers.value.length)
  const isFull = computed(() => parcelNumbers.value.length >= MAX_COMPARE)

  function has(parcelNumber: string): boolean {
    return parcelNumbers.value.includes(parcelNumber)
  }

  function add(parcelNumber: string): boolean {
    if (has(parcelNumber) || isFull.value) return false
    parcelNumbers.value = [...parcelNumbers.value, parcelNumber]
    return true
  }

  function remove(parcelNumber: string): void {
    parcelNumbers.value = parcelNumbers.value.filter((value) => value !== parcelNumber)
  }

  function toggle(parcelNumber: string): boolean {
    if (has(parcelNumber)) {
      remove(parcelNumber)
      return false
    }
    return add(parcelNumber)
  }

  function clear(): void {
    parcelNumbers.value = []
  }

  watch(
    parcelNumbers,
    (value) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
      } catch {
        return
      }
    },
    { deep: true },
  )

  return { parcelNumbers, count, isFull, has, add, remove, toggle, clear }
})
