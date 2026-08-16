<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { FreshnessStatus, SourceFreshness } from '@/lib/types'

const props = defineProps<{ parcelNumber: string | undefined }>()

const rows = ref<SourceFreshness[]>([])
const loading = ref(false)

const DAY_MS = 86_400_000

function ageDays(asOf: string | null): number | null {
  if (asOf === null) return null
  const parsed = Date.parse(asOf)
  if (Number.isNaN(parsed)) return null
  return Math.max(0, Math.floor((Date.now() - parsed) / DAY_MS))
}

function ageLabel(asOf: string | null): string {
  const days = ageDays(asOf)
  if (days === null) return 'Not loaded'
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days} days ago`
}

function tone(asOf: string | null): string {
  return asOf === null ? 'lot-text-faint' : 'lot-text-muted'
}

const STALE_LABEL: Record<FreshnessStatus, string> = {
  green: '',
  amber: 'overdue',
  red: 'stale',
}

function staleLabel(row: SourceFreshness): string {
  return row.freshness ? STALE_LABEL[row.freshness] : ''
}

const behind = computed(() =>
  rows.value.filter((row) => row.freshness === 'red' || row.freshness === 'amber'),
)

const loaded = computed(() => rows.value.filter((row) => row.as_of !== null).length)

async function load(parcelNumber: string | undefined): Promise<void> {
  rows.value = []
  if (!parcelNumber) return
  loading.value = true
  try {
    rows.value = await api.getParcelFreshness(parcelNumber)
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <q-card v-if="rows.length" flat bordered class="rounded-borders" data-test="freshness-panel">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="update" size="18px" class="q-mr-xs" />Source freshness
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          When each underlying source last loaded successfully for this market. A source shown as
          not loaded was never obtained, so anything depending on it is reported as unavailable
          rather than clear.
        </q-tooltip>
        <q-space />
        <q-badge
          v-if="behind.length"
          color="warning"
          text-color="black"
          data-test="freshness-behind"
        >
          {{ behind.length }} behind schedule
        </q-badge>
        <span v-else class="text-caption lot-text-muted"
          >{{ loaded }}/{{ rows.length }} loaded</span
        >
      </div>

      <div class="source-list">
        <div v-for="row in rows" :key="row.source_label" class="source-row">
          <span class="source-title">{{ row.title }}</span>
          <span class="source-age" :class="tone(row.as_of)">
            {{ ageLabel(row.as_of) }}
            <span
              v-if="staleLabel(row)"
              class="stale-flag"
              :class="`stale-${row.freshness}`"
              :data-test="`freshness-flag-${row.source_label}`"
              >{{ staleLabel(row) }}</span
            >
            <q-tooltip v-if="row.freshness_reason" max-width="260px">
              {{ row.freshness_reason }}
            </q-tooltip>
          </span>
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
  margin-bottom: 6px;
}
.source-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.06));
}
.source-row:last-child {
  border-bottom: none;
}
.source-title {
  font-size: 12.5px;
  color: var(--lot-ink);
}
.source-age {
  font-size: 12px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stale-flag {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 1px 6px;
  border-radius: var(--lot-radius-pill);
}
.stale-red {
  color: var(--lot-sev-high);
  background: var(--lot-negative-soft);
}
.stale-amber {
  color: var(--lot-sev-medium);
  background: var(--lot-warning-soft);
}
</style>
