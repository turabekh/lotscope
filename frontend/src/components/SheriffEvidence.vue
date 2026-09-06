<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import EvidenceSources from '@/components/EvidenceSources.vue'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { AnalystEnvelope } from '@/lib/types'

/**
 * This parcel's sheriff-sale listings and the changes recorded against them. A listing
 * whose status reads Postponed but whose date is still ahead is scheduled — the status
 * names the date that moved, not the case — so the row says which it is rather than
 * leaving the reader to interpret a status word.
 */
const props = defineProps<{ parcelNumber: string | undefined }>()

interface Listing {
  case_number: string | null
  sale_type: string | null
  sale_date: string | null
  status: string | null
  opening_bid: number | null
  plaintiff: string | null
  is_scheduled: boolean
}

interface Change {
  observed_at: string
  summary: string
}

const envelope = ref<AnalystEnvelope | null>(null)
const loading = ref(false)
const failed = ref(false)

const listings = computed<Listing[]>(
  () => (envelope.value?.data.listings as Listing[] | undefined) ?? [],
)
const changes = computed<Change[]>(
  () => (envelope.value?.data.changes as Change[] | undefined) ?? [],
)

function bid(value: number | null): string {
  return value === null || value === undefined ? '—' : formatCurrency(value)
}

async function load(parcelNumber: string | undefined): Promise<void> {
  envelope.value = null
  failed.value = false
  if (!parcelNumber) return
  loading.value = true
  try {
    envelope.value = await api.getEvidence(parcelNumber, 'sheriff')
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <div class="ev" data-test="sheriff-evidence">
    <p v-if="loading" class="ev__note">Loading the sheriff listing…</p>

    <p v-else-if="failed" class="ev__note" data-test="sheriff-unavailable">
      The sheriff listing could not be loaded. That is a gap in what we can show, not a statement
      that this lot is not listed.
    </p>

    <template v-else-if="envelope">
      <p v-if="!listings.length" class="ev__note" data-test="sheriff-empty">
        No sheriff-sale listing is on file for this parcel.
      </p>

      <table v-else class="ev__table" data-test="sheriff-table">
        <thead>
          <tr>
            <th>Sale date</th>
            <th>Case</th>
            <th>Type</th>
            <th>Status</th>
            <th class="ev__num">Opening bid</th>
            <th>Plaintiff</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(listing, index) in listings" :key="`${listing.case_number}-${index}`">
            <td>{{ listing.sale_date ?? 'no date recorded' }}</td>
            <td>{{ listing.case_number ?? '—' }}</td>
            <td>{{ listing.sale_type ?? '—' }}</td>
            <td>
              {{ listing.status ?? 'no status recorded' }}
              <span v-if="listing.is_scheduled" class="ev__label" data-test="sheriff-scheduled"
                >still scheduled</span
              >
            </td>
            <td class="ev__num">{{ bid(listing.opening_bid) }}</td>
            <td>{{ listing.plaintiff ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <ul v-if="changes.length" class="ev__changes" data-test="sheriff-changes">
        <li v-for="(change, index) in changes" :key="`${change.observed_at}-${index}`">
          {{ change.summary }}
          <span class="ev__label">seen {{ change.observed_at.slice(0, 10) }}</span>
        </li>
      </ul>

      <EvidenceSources :sources="envelope.sources" :unverified="envelope.unverified" />
    </template>
  </div>
</template>

<style scoped>
.ev__changes {
  margin: 8px 0 0;
  padding-left: 16px;
  font-size: 12px;
  line-height: 1.6;
}
</style>
