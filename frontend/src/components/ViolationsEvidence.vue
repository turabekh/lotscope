<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import EvidenceSources from '@/components/EvidenceSources.vue'
import { api } from '@/lib/api'
import type { AnalystEnvelope } from '@/lib/types'

/** L&I violations on this parcel: what is open, what is only on record. */
const props = defineProps<{ parcelNumber: string | undefined }>()

interface Violation {
  event_date: string | null
  status: string | null
  case_status: string | null
  description: string | null
  unsafe: boolean
  imminently_dangerous: boolean
}

interface Posture {
  violations_on_record: number
  open_violations: number
}

const envelope = ref<AnalystEnvelope | null>(null)
const loading = ref(false)
const failed = ref(false)

const posture = computed<Posture | null>(
  () => (envelope.value?.data.posture as Posture | undefined) ?? null,
)
const violations = computed<Violation[]>(
  () => (envelope.value?.data.violations as Violation[] | undefined) ?? [],
)

// Open versus on record is the distinction a buyer is actually asking about: a closed case
// is history, an open one is theirs on settlement day.
const lede = computed(() => {
  const counts = posture.value
  if (!counts) return ''
  if (counts.violations_on_record === 0) return 'No L&I violation is on record for this parcel.'
  const open = counts.open_violations
  const total = counts.violations_on_record
  const openText = open === 1 ? '1 is open' : `${open} are open`
  return `${total} violation${total === 1 ? '' : 's'} on record, ${open === 0 ? 'none open' : openText}.`
})

async function load(parcelNumber: string | undefined): Promise<void> {
  envelope.value = null
  failed.value = false
  if (!parcelNumber) return
  loading.value = true
  try {
    envelope.value = await api.getEvidence(parcelNumber, 'violations')
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <div class="ev" data-test="violations-evidence">
    <p v-if="loading" class="ev__note">Loading violations…</p>

    <p v-else-if="failed" class="ev__note" data-test="violations-unavailable">
      Violations could not be loaded. That is a gap in what we can show, not a clean record.
    </p>

    <template v-else-if="envelope">
      <p class="ev__lede" data-test="violations-lede">{{ lede }}</p>

      <table v-if="violations.length" class="ev__table" data-test="violations-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Case status</th>
            <th>What was cited</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(violation, index) in violations" :key="`${violation.event_date}-${index}`">
            <td>{{ violation.event_date ?? 'date not recorded' }}</td>
            <td>{{ violation.case_status ?? violation.status ?? 'status not recorded' }}</td>
            <td>
              {{ violation.description ?? 'no description recorded' }}
              <span
                v-if="violation.imminently_dangerous"
                class="ev__flag"
                data-test="violation-imminently-dangerous"
                >imminently dangerous</span
              >
              <span v-else-if="violation.unsafe" class="ev__flag" data-test="violation-unsafe"
                >unsafe</span
              >
            </td>
          </tr>
        </tbody>
      </table>

      <EvidenceSources :sources="envelope.sources" :unverified="envelope.unverified" />
    </template>
  </div>
</template>
