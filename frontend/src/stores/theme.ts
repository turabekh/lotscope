import { Dark } from 'quasar'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'lotscope.theme'
const MODES: ThemeMode[] = ['light', 'dark', 'auto']

function readStored(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'light' || raw === 'dark' || raw === 'auto' ? raw : 'auto'
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>('auto')

  function apply(next: ThemeMode): void {
    Dark.set(next === 'auto' ? 'auto' : next === 'dark')
  }

  function set(next: ThemeMode): void {
    mode.value = next
    localStorage.setItem(STORAGE_KEY, next)
    apply(next)
  }

  function cycle(): void {
    const index = MODES.indexOf(mode.value)
    set(MODES[(index + 1) % MODES.length])
  }

  function init(): void {
    set(readStored())
  }

  const isDark = computed(() => Dark.isActive)
  const icon = computed(() =>
    mode.value === 'auto' ? 'brightness_auto' : mode.value === 'dark' ? 'dark_mode' : 'light_mode',
  )
  const label = computed(() =>
    mode.value === 'auto' ? 'Auto theme' : mode.value === 'dark' ? 'Dark theme' : 'Light theme',
  )

  return { mode, isDark, icon, label, set, cycle, init }
})
