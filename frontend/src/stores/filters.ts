import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type UseClass = 'R' | 'C' | 'I' | 'S'

export interface UseClassOption {
  value: UseClass
  label: string
  color: string
}

export const USE_CLASS_OPTIONS: UseClassOption[] = [
  { value: 'R', label: 'Residential', color: '#1565c0' },
  { value: 'C', label: 'Commercial', color: '#c62828' },
  { value: 'I', label: 'Industrial', color: '#6a1b9a' },
  { value: 'S', label: 'Special', color: '#2e7d32' },
]

export const useFiltersStore = defineStore('filters', () => {
  const vacantOnly = ref(false)
  const useClasses = ref<UseClass[]>([])

  function toggleClass(value: UseClass): void {
    useClasses.value = useClasses.value.includes(value)
      ? useClasses.value.filter((item) => item !== value)
      : [...useClasses.value, value]
  }

  function reset(): void {
    vacantOnly.value = false
    useClasses.value = []
  }

  const activeCount = computed(
    () => (vacantOnly.value ? 1 : 0) + (useClasses.value.length > 0 ? 1 : 0),
  )

  return { vacantOnly, useClasses, toggleClass, reset, activeCount }
})
