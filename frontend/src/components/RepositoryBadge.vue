<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { RepositoryStatus } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const status = ref<RepositoryStatus | null>(null)

async function load(): Promise<void> {
  status.value = null
  try {
    status.value = await api.getRepositoryStatus(props.parcelNumber)
  } catch {
    status.value = null
  }
}

onMounted(load)
watch(() => props.parcelNumber, load)
</script>

<template>
  <div v-if="status?.in_repository" class="repo-badge">
    <div class="repo-head">
      <q-icon name="gavel" size="18px" class="q-mr-xs" />
      Repository — available from the county
      <q-badge v-if="status.bid_pending" color="orange-8" class="q-ml-sm">bid pending</q-badge>
      <q-badge v-if="status.city_status" color="blue-grey-6" class="q-ml-sm">
        {{ status.city_status }}
      </q-badge>
    </div>
    <div class="repo-detail">
      A county-held tax-repository parcel, purchasable over the counter: written bid, $2,000
      minimum plus fees, subject to approval by the county commissioners and taxing bodies, and
      conveyed with no post-sale redemption period.
      <template v-if="status.city_status">
        City status "{{ status.city_status }}" per the City Codes Administrator (as of
        2025-10-08); known only for repository-listed parcels — not citywide code-enforcement
        coverage.
      </template>
      <template v-if="status.list_as_of"> Repository list as of {{ status.list_as_of }}.</template>
    </div>
  </div>
</template>

<style scoped>
.repo-badge {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid var(--lot-border, #d5d9e0);
  border-radius: 8px;
  background: rgba(180, 130, 40, 0.06);
}
.repo-head {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}
.repo-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--lot-muted);
}
</style>
