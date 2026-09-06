<script setup lang="ts">
import { computed } from 'vue'

import ShowMe from '@/components/ShowMe.vue'
import VerdictHero from '@/components/VerdictHero.vue'
import VerdictPanel from '@/components/VerdictPanel.vue'
import type { ParcelChecklist, VerdictResult } from '@/lib/types'
import { provisionTarget, storedTarget } from '@/lib/sourceLinks'

// One verdict section. The headline and the dimensional reasoning used to be two cards
// that each announced themselves as the verdict; they are one thing said at two levels of
// detail, so they read as one now.
const props = defineProps<{
  verdict: VerdictResult
  developed?: boolean
  checklist?: ParcelChecklist | null
  citedSection?: string | null
}>()

// The dimensional standards the envelope applied. cited_section is the Title 14
// reference the buildability maths actually used, so that is what "Show me" opens.
const provision = computed(() =>
  provisionTarget(props.citedSection ?? null, props.citedSection ?? null),
)

const computedAt = computed(() =>
  storedTarget('lotscope_verdict', props.verdict.computed_at ?? null),
)
</script>

<template>
  <section class="verdict" data-test="lot-section-verdict">
    <header class="verdict__head">
      <h2 class="verdict__title">Verdict</h2>
      <ShowMe :target="computedAt" />
    </header>

    <VerdictHero :verdict="verdict" :developed="developed" :checklist="checklist" />

    <div class="verdict__detail">
      <div class="verdict__cite">
        <span class="verdict__label">Dimensional standards</span>
        <ShowMe :target="provision" data-test="verdict-provision" />
      </div>
      <VerdictPanel :verdict="verdict" :developed="developed" :checklist="checklist" />
    </div>
  </section>
</template>

<style scoped>
.verdict__head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 8px;
}
.verdict__title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}
.verdict__detail {
  margin-top: 12px;
}
.verdict__cite {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 6px;
}
.verdict__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--ls-muted, #6b7280);
}
</style>
