<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/lib/api'
import type { CorrectionRecord, CorrectionStatus } from '@/lib/types'

const FILTERS: Array<{ value: CorrectionStatus | null; label: string }> = [
  { value: 'open', label: 'Open' },
  { value: 'triaged', label: 'Triaged' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'rejected', label: 'Rejected' },
  { value: null, label: 'All' },
]

const STATUS_COLOR: Record<string, string> = {
  open: 'warning',
  triaged: 'info',
  resolved: 'positive',
  rejected: 'grey-6',
}

const TERMINAL: CorrectionStatus[] = ['resolved', 'rejected']

const filter = ref<CorrectionStatus | null>('open')
const records = ref<CorrectionRecord[]>([])
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const saving = ref<number | null>(null)
const notes = ref<Record<number, string>>({})

const isEmpty = computed(() => !loading.value && records.value.length === 0)

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    records.value = await api.getCorrectionQueue(filter.value ?? undefined)
  } catch {
    errorMessage.value = 'The correction queue could not be loaded.'
    records.value = []
  } finally {
    loading.value = false
  }
}

async function setStatus(record: CorrectionRecord, status: CorrectionStatus): Promise<void> {
  saving.value = record.id
  errorMessage.value = null
  try {
    const note = notes.value[record.id]?.trim()
    await api.triageCorrection(record.id, { status, resolution: note ? note : null })
    delete notes.value[record.id]
    await load()
  } catch {
    errorMessage.value = 'That correction could not be updated. Nothing was changed.'
  } finally {
    saving.value = null
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

onMounted(load)
</script>

<template>
  <q-card flat bordered class="queue" data-test="corrections-queue">
    <q-card-section class="q-py-sm">
      <div class="head">
        <div class="title">
          <q-icon name="flag" size="18px" class="q-mr-xs" />Reported corrections
        </div>
        <q-btn flat dense round icon="refresh" :loading="loading" @click="load" />
      </div>

      <q-btn-toggle
        v-model="filter"
        :options="FILTERS"
        dense
        unelevated
        no-caps
        size="sm"
        toggle-color="primary"
        class="q-mb-sm"
        data-test="corrections-filter"
        @update:model-value="load"
      />

      <div v-if="errorMessage" class="note error" data-test="corrections-error">
        {{ errorMessage }}
      </div>

      <div v-if="isEmpty" class="note" data-test="corrections-empty">
        No corrections with this status.
      </div>

      <div
        v-for="record in records"
        :key="record.id"
        class="record"
        :data-test="`correction-${record.id}`"
      >
        <div class="record-head">
          <q-badge :color="STATUS_COLOR[record.status] ?? 'grey-6'" text-color="white">
            {{ record.status }}
          </q-badge>
          <span class="parcel">{{ record.parcel_number }}</span>
          <span class="section">{{ record.section }}</span>
          <span v-if="record.field_name" class="field">· {{ record.field_name }}</span>
          <q-space />
          <span class="stamp">reported {{ formatDate(record.created_at) }}</span>
        </div>

        <div class="description">{{ record.description }}</div>

        <div class="evidence">
          <span>Verdict {{ record.verdict_version ?? 'unrecorded' }}</span>
          <span>computed {{ formatDate(record.verdict_computed_at) }}</span>
          <span>field state {{ record.field_status ?? 'unrecorded' }}</span>
          <span>source {{ record.source_label ?? 'unrecorded' }}</span>
          <span>as of {{ formatDate(record.source_as_of) }}</span>
        </div>

        <div v-if="record.resolution" class="resolution">
          <strong>{{ record.status === 'rejected' ? 'Reason' : 'Resolution' }}:</strong>
          {{ record.resolution }}
        </div>

        <div v-if="!TERMINAL.includes(record.status as CorrectionStatus)" class="actions">
          <q-input
            v-model="notes[record.id]"
            dense
            outlined
            type="textarea"
            autogrow
            label="Note to the reporter (optional)"
            :data-test="`correction-note-${record.id}`"
          />
          <div class="buttons">
            <q-btn
              v-if="record.status === 'open'"
              dense
              no-caps
              unelevated
              color="info"
              label="Mark triaged"
              :loading="saving === record.id"
              @click="setStatus(record, 'triaged')"
            />
            <q-btn
              dense
              no-caps
              unelevated
              color="positive"
              label="Resolve"
              :loading="saving === record.id"
              :data-test="`correction-resolve-${record.id}`"
              @click="setStatus(record, 'resolved')"
            />
            <q-btn
              dense
              no-caps
              outline
              color="grey-7"
              label="Reject"
              :loading="saving === record.id"
              :data-test="`correction-reject-${record.id}`"
              @click="setStatus(record, 'rejected')"
            />
          </div>
          <div class="note">
            Rejecting records that the report was reviewed and no change was made. It does not alter
            the parcel.
          </div>
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.queue {
  border-radius: var(--lot-radius);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.record {
  border-top: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.08));
  padding: 10px 0;
}
.record-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12.5px;
  flex-wrap: wrap;
}
.parcel {
  font-weight: 600;
}
.section,
.field {
  color: var(--lot-muted);
}
.stamp {
  font-size: 11.5px;
  color: var(--lot-muted);
}
.description {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.45;
}
.evidence {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11.5px;
  color: var(--lot-muted);
}
.resolution {
  margin-top: 6px;
  font-size: 12.5px;
}
.actions {
  margin-top: 8px;
  display: grid;
  gap: 6px;
}
.buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.note {
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.45;
}
.note.error {
  color: var(--lot-negative, #c10015);
}
</style>
