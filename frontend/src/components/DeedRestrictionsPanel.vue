<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import type { DeedRestrictionItem } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { deedRestrictions } = storeToRefs(store)

const show = computed(() => (deedRestrictions.value?.count ?? 0) > 0)

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
.deed-disclaimer {
  font-size: 11px;
  color: #90a4ae;
  margin-top: 8px;
}
</style>
