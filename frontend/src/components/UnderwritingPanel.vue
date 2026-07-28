<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { UnderwritingAnalysis } from '@/lib/types'

const props = defineProps<{ parcelNumber: string | undefined }>()

const analysis = ref<UnderwritingAnalysis | null>(null)
const loading = ref(false)
const showAssumptions = ref(false)

const ORIGIN_LABEL: Record<string, string> = {
  platform_default: 'Platform default',
  market_default: 'Market default',
  derived: 'Derived from this parcel',
  user_override: 'Your profile',
  authoritative_source: 'Source-reported',
}

const cases = computed(() => analysis.value?.cases ?? [])
const unavailable = computed(
  () => analysis.value?.assumptions.filter((a) => a.value === null) ?? [],
)
const overridden = computed(
  () => analysis.value?.assumptions.filter((a) => a.origin === 'user_override') ?? [],
)

function money(value: number | null): string {
  return value === null ? 'Not calculated' : formatCurrency(value)
}

function percent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`
}

function originLabel(origin: string): string {
  return ORIGIN_LABEL[origin] ?? origin
}

async function load(parcelNumber: string | undefined): Promise<void> {
  analysis.value = null
  if (!parcelNumber) return
  loading.value = true
  try {
    analysis.value = await api.getUnderwriting(parcelNumber)
  } catch {
    analysis.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <q-card v-if="analysis" flat bordered class="rounded-borders" data-test="underwriting-panel">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="calculate" size="18px" class="q-mr-xs" />Underwriting
        <q-space />
        <span v-if="overridden.length" class="text-caption text-primary">
          {{ overridden.length }} from your profile
        </span>
      </div>

      <div class="case-grid">
        <div v-for="item in cases" :key="item.case" class="case" :class="item.case">
          <div class="case-label">{{ item.label }}</div>
          <div class="case-mao lot-numeric">{{ money(item.max_allowable_offer) }}</div>
          <div class="case-margin">Margin {{ percent(item.margin) }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            {{ item.rationale }}
          </q-tooltip>
        </div>
      </div>

      <div v-if="unavailable.length" class="excluded" data-test="unavailable-inputs">
        <q-icon name="info" size="14px" class="q-mr-xs" />
        {{ unavailable.length }} input{{ unavailable.length > 1 ? 's are' : ' is' }} unavailable, so
        these figures exclude {{ unavailable.map((a) => a.name.replace(/_/g, ' ')).join(', ') }}.
      </div>

      <button type="button" class="disclose" @click="showAssumptions = !showAssumptions">
        {{ showAssumptions ? 'Hide' : 'Show' }} assumptions and formula
      </button>

      <div v-if="showAssumptions" class="disclosure" data-test="mao-disclosure">
        <div class="formula lot-numeric">{{ analysis.mao.formula }}</div>

        <div class="assumption-list">
          <div v-for="item in analysis.assumptions" :key="item.name" class="assumption">
            <span class="assumption-name">{{ item.name.replace(/_/g, ' ') }}</span>
            <span class="assumption-value lot-numeric">
              {{ item.value === null ? 'Unavailable' : item.value }}
            </span>
            <span class="assumption-origin">{{ originLabel(item.origin) }}</span>
            <q-tooltip v-if="item.limitations" max-width="260px">{{ item.limitations }}</q-tooltip>
          </div>
        </div>

        <div class="excluded">
          <strong>Not accounted for:</strong> {{ analysis.mao.exclusions.join('; ') }}.
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
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
  margin-bottom: 8px;
}
.case-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.case {
  padding: 8px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.03));
  text-align: center;
}
.case.base {
  outline: 2px solid var(--lot-accent, #1976d2);
}
.case-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
}
.case-mao {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
}
.case-margin {
  font-size: 11.5px;
  color: var(--lot-muted);
}
.excluded {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.4;
}
.disclose {
  margin-top: 8px;
  background: none;
  border: none;
  padding: 0;
  font-size: 12px;
  color: var(--lot-accent, #1976d2);
  cursor: pointer;
  text-decoration: underline;
}
.disclosure {
  margin-top: 8px;
}
.formula {
  font-size: 11.5px;
  padding: 6px 8px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
  color: var(--lot-ink);
  overflow-x: auto;
}
.assumption-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
}
.assumption {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.06));
}
.assumption-name {
  color: var(--lot-ink);
}
.assumption-value {
  color: var(--lot-ink);
  font-weight: 600;
}
.assumption-origin {
  font-size: 11px;
  color: var(--lot-muted);
}
</style>
