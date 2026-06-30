<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency } from '@/lib/format'
import type { DeedRestrictionItem, RecordedDeedItem } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { deedRestrictions } = storeToRefs(store)

const show = computed(
  () => (deedRestrictions.value?.count ?? 0) > 0 || (deedRestrictions.value?.deeds.length ?? 0) > 0,
)

function deeds(): RecordedDeedItem[] {
  return deedRestrictions.value?.deeds ?? []
}

const KIND_LABEL: Record<string, string> = {
  use_restriction: 'Use restriction',
  easement: 'Easement',
  covenant: 'Covenant',
  condition: 'Condition',
  access: 'Access',
  other: 'Other',
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'negative',
  medium: 'warning',
  low: 'grey-6',
}

function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind
}

function confidenceColor(confidence: string): string {
  return CONFIDENCE_COLOR[confidence] ?? 'grey-6'
}

function restrictions(): DeedRestrictionItem[] {
  return deedRestrictions.value?.restrictions ?? []
}
</script>

<template>
  <q-card v-if="show && deedRestrictions" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="gavel" size="18px" class="q-mr-xs" />Deed restrictions
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Restrictions, easements, and covenants extracted from recorded deeds by AI. Informational
          only — not a title determination. Confirm with the recorded document, a title company, or
          counsel.
        </q-tooltip>
      </div>

      <div class="deed-list">
        <div v-for="(item, index) in restrictions()" :key="index" class="deed-row">
          <div class="deed-head">
            <q-chip dense square color="blue-grey-7" text-color="white" class="deed-kind">
              {{ kindLabel(item.kind) }}
            </q-chip>
            <q-badge :color="confidenceColor(item.confidence)" text-color="white">
              {{ item.confidence }}
            </q-badge>
            <q-space />
            <span v-if="item.recording_date" class="deed-date">{{ item.recording_date }}</span>
          </div>
          <div class="deed-text">{{ item.text }}</div>
          <div v-if="item.citation" class="deed-cite">“{{ item.citation }}”</div>
        </div>
      </div>

      <div v-if="deeds().length" class="records">
        <div class="records-title">Recorded documents</div>
        <a
          v-for="deed in deeds()"
          :key="deed.document_id"
          class="record-row"
          :href="deed.record_url ?? undefined"
          target="_blank"
          rel="noopener noreferrer"
        >
          <q-icon name="description" size="16px" class="q-mr-xs text-blue-grey-5" />
          <span class="record-type">{{ deed.document_type ?? 'Document' }}</span>
          <span v-if="deed.recording_date" class="record-date">{{ deed.recording_date }}</span>
          <span v-if="deed.sale_price" class="record-price">{{
            formatCurrency(deed.sale_price)
          }}</span>
          <q-space />
          <q-icon name="open_in_new" size="14px" class="text-blue-grey-4" />
        </a>
        <div class="records-note">Links open the official PhilaDox record (login may be required).</div>
      </div>

      <div class="deed-disclaimer">
        Informational only — not legal advice. Verify against the recorded deed.
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
  color: #5b6b7d;
  margin-bottom: 6px;
}
.deed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.deed-row {
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: #fff8f6;
  border: 1px solid #ffd9cf;
}
.deed-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.deed-kind {
  font-size: 11px;
}
.deed-date {
  font-size: 11px;
  color: #90a4ae;
}
.deed-text {
  font-size: 13px;
  color: #1f2933;
  margin-top: 4px;
}
.deed-cite {
  font-size: 11.5px;
  color: #78909c;
  font-style: italic;
  margin-top: 2px;
}
.records {
  margin-top: 10px;
}
.records-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #7b8794;
  margin-bottom: 4px;
}
.record-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--lot-radius-sm);
  background: #f4f6f8;
  margin-bottom: 4px;
  text-decoration: none;
  color: #1f2933;
}
.record-row:hover {
  background: #e9eef3;
}
.record-type {
  font-size: 12.5px;
  font-weight: 600;
}
.record-date,
.record-price {
  font-size: 11.5px;
  color: #607d8b;
}
.records-note {
  font-size: 10.5px;
  color: #a0aab3;
  margin-top: 2px;
}
.deed-disclaimer {
  font-size: 11px;
  color: #90a4ae;
  margin-top: 8px;
}
</style>
