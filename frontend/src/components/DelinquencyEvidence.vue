<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import EvidenceSources from '@/components/EvidenceSources.vue'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { AnalystEnvelope } from '@/lib/types'

/**
 * The tax posture of a parcel, and who the debt is recorded against. The named debtor is
 * the point: a debt against a prior owner may have been discharged at a sheriff sale, so
 * the section says who it names rather than implying the current owner owes it.
 */
const props = defineProps<{ parcelNumber: string | undefined }>()

interface TaxRow {
  is_delinquent?: boolean | null
  total_due?: number | string | null
  principal_due?: number | string | null
  years_owed?: number | null
  lien_count?: number | null
  as_of_date?: string | null
  delinquency_owner?: string | null
  snapshot_period?: string | null
}

const envelope = ref<AnalystEnvelope | null>(null)
const loading = ref(false)
const failed = ref(false)

const tax = computed<TaxRow>(() => (envelope.value?.data.tax as TaxRow | undefined) ?? {})
const attribution = computed<string | null>(
  () => (envelope.value?.data.attribution as string | null | undefined) ?? null,
)
const hasTax = computed(() => Object.keys(tax.value).length > 0)

// Decimals cross the wire as strings, the way the Analyst receives them.
function money(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const parsed = typeof value === 'string' ? Number.parseFloat(value) : value
  return Number.isNaN(parsed) ? '—' : formatCurrency(parsed)
}

const posture = computed(() => {
  if (!hasTax.value) return 'No tax record is on file for this parcel.'
  return tax.value.is_delinquent
    ? `Delinquent — ${money(tax.value.total_due)} recorded as due.`
    : 'Not recorded as delinquent.'
})

async function load(parcelNumber: string | undefined): Promise<void> {
  envelope.value = null
  failed.value = false
  if (!parcelNumber) return
  loading.value = true
  try {
    envelope.value = await api.getEvidence(parcelNumber, 'delinquency')
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.parcelNumber, load, { immediate: true })
</script>

<template>
  <div class="ev" data-test="delinquency-evidence">
    <p v-if="loading" class="ev__note">Loading the tax posture…</p>

    <p v-else-if="failed" class="ev__note" data-test="delinquency-unavailable">
      The tax posture could not be loaded. That is a gap in what we can show, not a clear title.
    </p>

    <template v-else-if="envelope">
      <p class="ev__lede" data-test="delinquency-posture">{{ posture }}</p>

      <div v-if="hasTax" class="ev__kv" data-test="delinquency-facts">
        <div>
          <span class="ev__label">Principal</span>
          <span>{{ money(tax.principal_due) }}</span>
        </div>
        <div>
          <span class="ev__label">Years owed</span>
          <span>{{ tax.years_owed ?? '—' }}</span>
        </div>
        <div>
          <span class="ev__label">Liens</span>
          <span>{{ tax.lien_count ?? '—' }}</span>
        </div>
        <div>
          <span class="ev__label">Recorded against</span>
          <span data-test="delinquency-debtor">{{
            tax.delinquency_owner ?? 'no name recorded'
          }}</span>
        </div>
        <div>
          <span class="ev__label">Measured</span>
          <span>{{ tax.as_of_date ?? 'no as-of recorded' }}</span>
        </div>
      </div>

      <p v-if="attribution" class="ev__note" data-test="delinquency-attribution">
        {{ attribution }}
      </p>

      <EvidenceSources :sources="envelope.sources" :unverified="envelope.unverified" />
    </template>
  </div>
</template>
