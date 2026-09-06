<script setup lang="ts">
import { computed } from 'vue'

import ShowMe from '@/components/ShowMe.vue'
import { type ShowMeTarget, storedTarget } from '@/lib/sourceLinks'
import type { AnalystSource } from '@/lib/types'

/**
 * The provenance foot of an evidence section: one line per dataset behind it, plus what
 * the section could not establish. Sources come from the same envelope the Analyst cites,
 * so a fact on the page and a fact in the conversation name the same origin.
 */
const props = defineProps<{ sources: AnalystSource[]; unverified: string[] }>()

function asOf(source: AnalystSource): string | null {
  return source.fetched_at ?? source.ingested_at ?? source.computed_at ?? null
}

function stamp(source: AnalystSource): string {
  const when = asOf(source)
  if (!when) return 'no as-of recorded'
  const day = when.slice(0, 10)
  if (source.fetched_at) return `read live ${day}`
  if (source.computed_at) return `computed ${day}`
  return `ingested ${day}`
}

function target(source: AnalystSource): ShowMeTarget {
  return source.url
    ? { kind: 'external', label: source.name, url: source.url }
    : storedTarget(source.name, asOf(source))
}

const rows = computed(() => props.sources.map((source) => ({ source, target: target(source) })))
</script>

<template>
  <footer class="ev-sources" data-test="evidence-sources">
    <ul v-if="unverified.length" class="ev-sources__unverified" data-test="evidence-unverified">
      <!-- Named here because the tool could not establish it. It is unverified, not a finding. -->
      <li v-for="line in unverified" :key="line">{{ line }}</li>
    </ul>

    <div
      v-for="row in rows"
      :key="`${row.source.name}-${stamp(row.source)}`"
      class="ev-sources__row"
    >
      <span class="ev-sources__name">{{ row.source.name }}</span>
      <span class="ev-sources__stamp">{{ stamp(row.source) }}</span>
      <ShowMe :target="row.target" />
    </div>
  </footer>
</template>

<style scoped>
.ev-sources {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--lot-border);
}
.ev-sources__unverified {
  margin: 0 0 6px;
  padding-left: 16px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--lot-muted);
}
.ev-sources__row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11.5px;
  color: var(--lot-muted);
}
.ev-sources__name {
  font-weight: 600;
}
</style>
