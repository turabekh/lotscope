<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { VarianceOutlook } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const outlook = ref<VarianceOutlook | null>(null)
let requestToken = 0

async function load(): Promise<void> {
  const token = ++requestToken
  const parcelNumber = props.parcelNumber
  outlook.value = null
  try {
    const result = await api.getVarianceOutlook(parcelNumber)
    if (token === requestToken && result.parcel_number === props.parcelNumber) {
      outlook.value = result
    }
  } catch {
    if (token === requestToken) outlook.value = null
  }
}

onMounted(load)
watch(() => props.parcelNumber, load)

function pct(rate: number): string {
  return `${Math.round(rate * 100)}%`
}
</script>

<template>
  <div v-if="outlook" class="variance-outlook">
    <q-icon name="gavel" size="15px" class="q-mr-xs" />
    <template v-if="outlook.grant_rate != null">
      ZBA granted <strong>{{ pct(outlook.grant_rate) }}</strong> of {{ outlook.decided }} decided
      appeals for {{ outlook.district }} parcels in the last {{ outlook.window_months }} months.
      <span v-if="outlook.local_grant_rate != null && outlook.local_decided != null">
        In {{ outlook.local_scope }}: {{ pct(outlook.local_grant_rate) }} of
        {{ outlook.local_decided }}.
      </span>
      <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
        Population: {{ outlook.population_label }}. Empirical outcomes from recorded ZBA decisions —
        informational, not a prediction or advice.
      </q-tooltip>
    </template>
    <span v-else class="variance-thin">{{ outlook.reason }}</span>
  </div>
</template>

<style scoped>
.variance-outlook {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lot-muted);
  line-height: 1.4;
}
.variance-outlook strong {
  color: var(--lot-ink);
}
.variance-thin {
  color: var(--lot-faint);
}
</style>
