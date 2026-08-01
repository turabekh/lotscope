import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

const STORAGE_KEY = 'lotscope.compare'
const LABEL_KEY = 'lotscope.compare.labels'
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

function loadLabels(): Record<string, string> {
  try {
    const raw = localStorage.getItem(LABEL_KEY)
    if (raw === null) return {}
    const parsed: unknown = JSON.parse(raw)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed as Record<string, string>
  } catch {
    return {}
  }
}

export function shortParcelLabel(parcelNumber: string): string {
  const [, local] = parcelNumber.split(':')
  return local ?? parcelNumber
}

export const useCompareStore = defineStore('compare', () => {
  const parcelNumbers = ref<string[]>(loadInitial())
  const labels = ref<Record<string, string>>(loadLabels())

  const count = computed(() => parcelNumbers.value.length)
  const isFull = computed(() => parcelNumbers.value.length >= MAX_COMPARE)

  function has(parcelNumber: string): boolean {
    return parcelNumbers.value.includes(parcelNumber)
  }

  function add(parcelNumber: string, label?: string | null): boolean {
    if (has(parcelNumber) || isFull.value) return false
    parcelNumbers.value = [...parcelNumbers.value, parcelNumber]
    if (label) labels.value = { ...labels.value, [parcelNumber]: label }
    return true
  }

  function labelFor(parcelNumber: string): string {
    return labels.value[parcelNumber] ?? shortParcelLabel(parcelNumber)
  }

  function remove(parcelNumber: string): void {
    parcelNumbers.value = parcelNumbers.value.filter((value) => value !== parcelNumber)
  }

  function toggle(parcelNumber: string, label?: string | null): boolean {
    if (has(parcelNumber)) {
      remove(parcelNumber)
      return false
    }
    return add(parcelNumber, label)
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

  watch(
    labels,
    (value) => {
      try {
        localStorage.setItem(LABEL_KEY, JSON.stringify(value))
      } catch {
        return
      }
    },
    { deep: true },
  )

  return { parcelNumbers, labels, count, isFull, has, add, remove, toggle, clear, labelFor }
})
