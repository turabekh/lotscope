<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import EvidenceSources from '@/components/EvidenceSources.vue'
import ShowMe from '@/components/ShowMe.vue'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import { deedTarget } from '@/lib/sourceLinks'
import type { AnalystEnvelope } from '@/lib/types'

/** Every recorded transfer of this parcel, newest first, as the recorder has it. */
const props = defineProps<{ parcelNumber: string | undefined }>()

interface Deed {
  sale_date: string | null
  consideration: number | null
  document_type: string | null
  document_id: string | null
  grantor: string | null
  grantee: string | null
}

const envelope = ref<AnalystEnvelope | null>(null)
const loading = ref(false)
const failed = ref(false)

const deeds = computed<Deed[]>(() => (envelope.value?.data.deeds as Deed[] | undefined) ?? [])

function money(value: number | null): string {
  // A recorded consideration of nothing is a real thing — a nominal transfer — and saying
  // "$0" is more honest than a dash that reads as missing data.
  return value === null || value === undefined ? '—' : formatCurrency(value)
}

async function load(parcelNumber: string | undefined): Promise<void> {
  envelope.value = null
  failed.value = false
  if (!parcelNumber) return
  loading.value = true
  try {
    envelope.value = await api.getEvidence(parcelNumber, 'deeds')
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <div class="ev" data-test="deeds-evidence">
    <p v-if="loading" class="ev__note">Loading the deed chain…</p>

    <p v-else-if="failed" class="ev__note" data-test="deeds-unavailable">
      The deed chain could not be loaded. That is a gap in what we can show, not a statement that no
      deed exists.
    </p>

    <template v-else-if="envelope">
      <p v-if="!deeds.length" class="ev__note" data-test="deeds-empty">
        No recorded transfer is on file for this parcel.
      </p>

      <table v-else class="ev__table" data-test="deeds-table">
        <thead>
          <tr>
            <th>Recorded</th>
            <th>Type</th>
            <th class="ev__num">Consideration</th>
            <th>From</th>
            <th>To</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(deed, index) in deeds" :key="`${deed.document_id}-${index}`">
            <td>{{ deed.sale_date ?? 'date not recorded' }}</td>
            <td>{{ deed.document_type ?? '—' }}</td>
            <td class="ev__num">{{ money(deed.consideration) }}</td>
            <td>{{ deed.grantor ?? 'no party name recorded' }}</td>
            <td>{{ deed.grantee ?? 'no party name recorded' }}</td>
            <td>
              <ShowMe
                v-if="parcelNumber"
                :target="deedTarget(parcelNumber, deed.document_id)"
                :data-test="`deed-show-me-${index}`"
              />
            </td>
          </tr>
        </tbody>
      </table>

      <EvidenceSources :sources="envelope.sources" :unverified="envelope.unverified" />
    </template>
  </div>
</template>
