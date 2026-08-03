<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import type { FieldState } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { checklist } = storeToRefs(useParcelStore())

const program = computed(() => checklist.value?.program ?? null)

const STATE_STYLE: Record<FieldState, { color: string; hint: string }> = {
  verified: {
    color: 'positive',
    hint: 'Read directly from a city source or the district standards.',
  },
  calculated: {
    color: 'primary',
    hint: 'Computed by LotScope from the recorded standards and lot geometry.',
  },
  estimated: {
    color: 'warning',
    hint: 'An approximation from a proxy rule, not a measured figure.',
  },
  unavailable: {
    color: 'grey-6',
    hint: 'No value could be established; this is not a zero.',
  },
}
</script>

<template>
  <q-card v-if="program" flat bordered class="lot-card" data-test="program-panel">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="foundation" size="18px" class="q-mr-xs" />What can be built here
      </div>

      <p class="program-statement" data-test="program-statement">{{ program.statement }}</p>

      <div v-if="program.citation" class="program-citation" data-test="program-citation">
        <q-icon name="menu_book" size="14px" class="q-mr-xs" />{{ program.citation }}
      </div>

      <div v-if="program.claims.length" class="claim-grid" data-test="program-claims">
        <div v-for="claim in program.claims" :key="claim.label" class="claim">
          <div class="claim-label">{{ claim.label }}</div>
          <div class="claim-value lot-numeric">{{ claim.value }}</div>
          <q-badge :color="STATE_STYLE[claim.state].color" outline class="claim-state">
            {{ claim.state }}
            <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
              {{ STATE_STYLE[claim.state].hint }}
            </q-tooltip>
          </q-badge>
        </div>
      </div>

      <ul v-if="program.conditions.length" class="condition-list" data-test="program-conditions">
        <li v-for="condition in program.conditions" :key="condition">{{ condition }}</li>
      </ul>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.lot-card {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.section-title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.program-statement {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--lot-ink);
}
.program-citation {
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--lot-muted);
  display: flex;
  align-items: center;
}
.claim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  margin-top: 10px;
}
.claim {
  border: 1px solid var(--lot-border, rgba(128, 128, 128, 0.25));
  border-radius: 8px;
  padding: 6px 8px;
}
.claim-label {
  font-size: 11px;
  color: var(--lot-muted);
}
.claim-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--lot-ink);
  margin: 1px 0 3px;
}
.claim-state {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.condition-list {
  margin: 10px 0 0;
  padding-left: 16px;
  font-size: 11.5px;
  line-height: 1.45;
  color: var(--lot-muted);
}
</style>
