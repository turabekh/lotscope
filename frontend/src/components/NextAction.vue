<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import type { LeadItem } from '@/lib/types'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const props = defineProps<{ topLead: LeadItem | null }>()

const { searches } = storeToRefs(useSavedSearchesStore())
const { items: watchItems } = storeToRefs(useWatchlistStore())

interface Action {
  kind: string
  eyebrow: string
  headline: string
  detail: string
  cta: string
  icon: string
  to: RouteLocationRaw
}

const newMatches = computed(() =>
  searches.value.reduce((total, search) => total + Math.max(0, search.new_count), 0),
)

const alertedLots = computed(() => watchItems.value.filter((item) => item.has_alerts).length)

function leadDetail(lead: LeadItem): string {
  const reason = lead.top_factors[0] ?? lead.base_zoning_code
  const base = `Your strongest motivated-seller lead today · score ${Math.round(lead.score)}`
  return reason ? `${base} · ${reason}.` : `${base}.`
}

const action = computed<Action>(() => {
  if (newMatches.value > 0) {
    const plural = newMatches.value === 1 ? 'lot matches' : 'lots match'
    return {
      kind: 'matches',
      eyebrow: 'Start here',
      headline: `${newMatches.value} new ${plural} your saved searches`,
      detail: 'Screened against your buy box since you last looked.',
      cta: 'Review matches',
      icon: 'bolt',
      to: { name: 'lists', query: { tab: 'searches' } },
    }
  }

  if (alertedLots.value > 0) {
    const plural = alertedLots.value === 1 ? 'lot has' : 'lots have'
    return {
      kind: 'alerts',
      eyebrow: 'Start here',
      headline: `${alertedLots.value} saved ${plural} changed`,
      detail: 'Distress, liens or scores moved on lots you are tracking.',
      cta: 'See what changed',
      icon: 'notifications_active',
      to: { name: 'lists', query: { tab: 'lots' } },
    }
  }

  if (props.topLead !== null) {
    return {
      kind: 'lead',
      eyebrow: 'Start here',
      headline: props.topLead.address ?? props.topLead.parcel_number,
      detail: leadDetail(props.topLead),
      cta: 'Open the verdict',
      icon: 'trending_up',
      to: {
        name: 'parcel',
        params: { id: props.topLead.parcel_number },
      },
    }
  }

  return {
    kind: 'explore',
    eyebrow: 'Start here',
    headline: 'Find your next lot',
    detail: 'Search the map, or set a buy box and let matches come to you.',
    cta: 'Find lots',
    icon: 'travel_explore',
    to: { name: 'explore' },
  }
})
</script>

<template>
  <router-link :to="action.to" class="next" :data-test="`next-action-${action.kind}`">
    <div class="next-icon"><q-icon :name="action.icon" size="22px" /></div>
    <div class="next-body">
      <div class="next-eyebrow">{{ action.eyebrow }}</div>
      <div class="next-headline">{{ action.headline }}</div>
      <div class="next-detail">{{ action.detail }}</div>
    </div>
    <div class="next-cta">
      {{ action.cta }}
      <q-icon name="chevron_right" size="18px" />
    </div>
  </router-link>
</template>

<style scoped>
.next {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: var(--lot-radius);
  border: 1px solid var(--lot-accent-soft);
  background: var(--lot-accent-soft);
  color: var(--lot-ink);
  text-decoration: none;
}
.next:hover {
  border-color: var(--lot-accent);
}
.next-icon {
  flex: none;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--lot-accent);
  color: var(--lot-on-accent);
}
.next-body {
  min-width: 0;
  flex: 1;
}
.next-eyebrow {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--lot-accent-ink, var(--lot-accent));
}
.next-headline {
  font-weight: 700;
  font-size: 15px;
  line-height: 1.25;
  margin-top: 2px;
}
.next-detail {
  font-size: 12px;
  line-height: 1.4;
  color: var(--lot-muted);
  margin-top: 2px;
}
.next-cta {
  flex: none;
  display: none;
  align-items: center;
  gap: 2px;
  font-size: 13px;
  font-weight: 700;
  color: var(--lot-accent-ink, var(--lot-accent));
}
@media (min-width: 600px) {
  .next-cta {
    display: flex;
  }
}
</style>
