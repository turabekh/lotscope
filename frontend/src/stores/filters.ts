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

export type ColorMode = 'vacancy' | 'opportunity' | 'risk'

export const COLOR_MODE_OPTIONS: { value: ColorMode; label: string; icon: string }[] = [
  { value: 'vacancy', label: 'Vacancy', icon: 'grass' },
  { value: 'opportunity', label: 'Opportunity', icon: 'trending_up' },
  { value: 'risk', label: 'Risk', icon: 'warning_amber' },
]

export const useFiltersStore = defineStore('filters', () => {
  const vacantOnly = ref(false)
  const useClasses = ref<UseClass[]>([])
  const colorMode = ref<ColorMode>('vacancy')
  const show3d = ref(false)

  function toggleClass(value: UseClass): void {
    useClasses.value = useClasses.value.includes(value)
      ? useClasses.value.filter((item) => item !== value)
      : [...useClasses.value, value]
  }

  function reset(): void {
    vacantOnly.value = false
    useClasses.value = []
    colorMode.value = 'vacancy'
  }

  const activeCount = computed(
    () => (vacantOnly.value ? 1 : 0) + (useClasses.value.length > 0 ? 1 : 0),
  )

  return { vacantOnly, useClasses, colorMode, show3d, toggleClass, reset, activeCount }
})
