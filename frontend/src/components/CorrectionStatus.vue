<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '@/lib/api'
import type { CorrectionRecord } from '@/lib/types'

const records = ref<CorrectionRecord[]>([])
const loading = ref(true)
const failed = ref(false)

const STATUS_LABEL: Record<string, string> = {
  open: 'Received',
  triaged: 'Being reviewed',
  resolved: 'Corrected',
  rejected: 'Reviewed, no change',
}

const STATUS_COLOR: Record<string, string> = {
  open: 'grey',
  triaged: 'warning',
  resolved: 'positive',
  rejected: 'grey-7',
}

function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

function statusColor(status: string): string {
  return STATUS_COLOR[status] ?? 'grey'
}

onMounted(async () => {
  try {
    records.value = await api.getOwnCorrections()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <q-card flat bordered class="rounded-borders" data-test="correction-status">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="flag_circle" size="18px" class="q-mr-xs" />Data you reported
      </div>

      <div v-if="loading" class="note">Loading…</div>

      <div v-else-if="failed" class="note" data-test="correction-status-failed">
        Your reports could not be loaded just now. This does not affect any report you have already
        sent.
      </div>

      <div v-else-if="records.length === 0" class="note">
        You have not reported any incorrect data yet. Use “Report a correction” on any parcel when
        something looks wrong.
      </div>

      <div v-for="record in records" v-else :key="record.id" class="record">
        <div class="record-head">
          <router-link
            :to="{
              name: 'parcel',
              params: { market: record.market_code, id: record.parcel_number },
            }"
            class="record-parcel"
          >
            {{ record.parcel_number }}
          </router-link>
          <q-badge :color="statusColor(record.status)" :label="statusLabel(record.status)" />
        </div>
        <div class="record-desc">{{ record.description }}</div>
        <div v-if="record.resolution" class="record-resolution">
          <strong>Our reply:</strong> {{ record.resolution }}
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
.note {
  font-size: 12px;
  color: var(--lot-muted);
  line-height: 1.45;
}
.record {
  padding: 8px 0;
  border-bottom: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.07));
}
.record:last-child {
  border-bottom: none;
}
.record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.record-parcel {
  font-size: 13px;
  font-weight: 600;
  color: var(--lot-ink);
  text-decoration: none;
}
.record-parcel:hover {
  text-decoration: underline;
}
.record-desc {
  font-size: 12px;
  color: var(--lot-muted);
  line-height: 1.4;
  margin-top: 2px;
}
.record-resolution {
  font-size: 12px;
  color: var(--lot-ink);
  line-height: 1.4;
  margin-top: 4px;
}
</style>
