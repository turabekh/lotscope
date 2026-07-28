import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const VERDICT_SEEN_KEY = 'lotscope.firstSteps.verdictSeen'

export interface FirstStep {
  code: string
  label: string
  detail: string
  done: boolean
  routeName: string
  marketScoped: boolean
}

export const useFirstStepsStore = defineStore('firstSteps', () => {
  const verdictSeen = ref(localStorage.getItem(VERDICT_SEEN_KEY) === 'true')
  const assumptionsSet = ref(false)
  const resolved = ref(false)

  const watchlist = useWatchlistStore()
  const savedSearches = useSavedSearchesStore()

  function markVerdictSeen(): void {
    if (verdictSeen.value) return
    verdictSeen.value = true
    localStorage.setItem(VERDICT_SEEN_KEY, 'true')
  }

  async function refresh(): Promise<void> {
    await Promise.all([watchlist.ensureLoaded(), savedSearches.ensureLoaded()])
    try {
      const profiles = await api.listUnderwritingProfiles()
      assumptionsSet.value = profiles.some(
        (profile) => Object.keys(profile.assumptions ?? {}).length > 0,
      )
    } catch {
      assumptionsSet.value = false
    }
    resolved.value = true
  }

  const hasSavedLot = computed(() => watchlist.items.length > 0)
  const hasAlert = computed(() =>
    savedSearches.searches.some((search) => search.alerts_enabled === true),
  )

  const steps = computed<FirstStep[]>(() => [
    {
      code: 'verdict',
      label: 'Open a Parcel Verdict',
      detail: 'See what can be built on a lot, what it is worth, and what is wrong with it.',
      done: verdictSeen.value,
      routeName: 'explore',
      marketScoped: true,
    },
    {
      code: 'assumptions',
      label: 'Set your underwriting assumptions',
      detail: 'Your construction costs and target margin drive every offer figure we show you.',
      done: assumptionsSet.value,
      routeName: 'account',
      marketScoped: false,
    },
    {
      code: 'save',
      label: 'Save a lot',
      detail: 'Keep the lots you are working on in one place.',
      done: hasSavedLot.value,
      routeName: 'lists',
      marketScoped: true,
    },
    {
      code: 'alert',
      label: 'Turn on an alert',
      detail: 'Get told when a lot matching your search appears or changes.',
      done: hasAlert.value,
      routeName: 'lists',
      marketScoped: true,
    },
  ])

  const completed = computed(() => steps.value.filter((step) => step.done).length)
  const allDone = computed(() => completed.value === steps.value.length)

  return {
    steps,
    completed,
    allDone,
    resolved,
    verdictSeen,
    assumptionsSet,
    markVerdictSeen,
    refresh,
  }
})
