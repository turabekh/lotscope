<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { SkipTraceResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const $q = useQuasar()
const store = useParcelStore()
const { ownerPortfolio, detail } = storeToRefs(store)

const tracing = ref(false)
const traceResult = ref<SkipTraceResult | null>(null)

async function skipTrace(): Promise<void> {
  const parcelNumber = detail.value?.parcel_number
  if (!parcelNumber) return
  tracing.value = true
  try {
    const result = await api.skipTrace(parcelNumber)
    traceResult.value = result
    if (result.contacts.phones.length === 0 && result.contacts.emails.length === 0) {
      $q.notify({ type: 'info', message: 'No contact info found for this owner.' })
    }
  } catch (cause) {
    $q.notify({
      type: 'negative',
      message: cause instanceof ApiError ? cause.message : 'Skip trace failed.',
    })
  } finally {
    tracing.value = false
  }
}

const show = computed(() => ownerPortfolio.value !== null && ownerPortfolio.value.total_count > 1)
const soleHolding = computed(
  () => ownerPortfolio.value !== null && ownerPortfolio.value.total_count <= 1,
)
const moreCount = computed(() => {
  const p = ownerPortfolio.value
  if (p === null) return 0
  return Math.max(0, p.total_count - 1 - p.parcels.length)
})

function selectParcel(parcelNumber: string): void {
  void store.select(parcelNumber)
}
</script>

<template>
  <q-card
    v-if="soleHolding && ownerPortfolio"
    flat
    bordered
    class="rounded-borders"
    data-test="owner-sole-holding"
  >
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="account_balance_wallet" size="18px" class="q-mr-xs" />Owner portfolio
      </div>
      <div class="owner-name ellipsis">{{ ownerPortfolio.owner }}</div>
      <div class="sole-note">
        This is the only Philadelphia parcel recorded to this owner, so there is no assemblage or
        portfolio signal here. Owner names are matched as recorded, so spelling variants may split a
        portfolio.
      </div>
    </q-card-section>
  </q-card>

  <q-card
    v-else-if="show && ownerPortfolio"
    flat
    bordered
    class="rounded-borders"
    data-test="owner-portfolio-list"
  >
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="account_balance_wallet" size="18px" class="q-mr-xs" />Owner portfolio
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          Other Philadelphia parcels held by the same owner of record — an assemblage and
          motivated-seller signal. Owner names are matched as recorded, so spelling variants may
          split a portfolio.
        </q-tooltip>
      </div>

      <div class="owner-name ellipsis">{{ ownerPortfolio.owner }}</div>

      <div class="q-mt-xs">
        <q-btn
          outline
          dense
          no-caps
          size="sm"
          color="primary"
          icon="contact_phone"
          :label="traceResult ? 'Owner contacts' : 'Skip trace owner (1 credit)'"
          :loading="tracing"
          :disable="traceResult !== null"
          @click="skipTrace"
        />
        <div v-if="traceResult" class="trace-card q-mt-xs">
          <div v-if="traceResult.contacts.phones.length" class="trace-line">
            <q-icon name="call" size="14px" /> {{ traceResult.contacts.phones.join(', ') }}
          </div>
          <div v-if="traceResult.contacts.emails.length" class="trace-line">
            <q-icon name="mail" size="14px" /> {{ traceResult.contacts.emails.join(', ') }}
          </div>
          <div
            v-if="!traceResult.contacts.phones.length && !traceResult.contacts.emails.length"
            class="trace-line lot-text-muted"
          >
            No contact info on record.
          </div>
          <div class="trace-note">
            Not for credit, employment, insurance, or tenant-screening use.
          </div>
        </div>
      </div>

      <div class="row q-col-gutter-sm q-mt-xs">
        <div class="col-4 stat">
          <div class="stat-label">Parcels</div>
          <div class="stat-value">{{ ownerPortfolio.total_count }}</div>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Vacant</div>
          <div class="stat-value">{{ ownerPortfolio.vacant_count }}</div>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Assessed</div>
          <div class="stat-value">{{ formatCurrency(ownerPortfolio.total_market_value) }}</div>
        </div>
      </div>

      <div class="owner-list q-mt-sm">
        <div
          v-for="lot in ownerPortfolio.parcels"
          :key="lot.parcel_number"
          class="owner-row"
          @click="selectParcel(lot.parcel_number)"
        >
          <div class="owner-body">
            <div class="owner-addr ellipsis">{{ lot.address ?? lot.parcel_number }}</div>
            <div class="owner-meta">
              {{ lot.base_zoning_code ?? 'No zoning' }}
              <span v-if="lot.is_vacant" class="text-amber-9">· Vacant</span>
              <span v-if="lot.market_value"> · {{ formatCurrency(lot.market_value) }}</span>
            </div>
          </div>
          <!-- The one score on this page that is not computed for this read: it comes from
               the nightly screen, so the badge says so rather than asserting it. -->
          <q-badge
            v-if="lot.opportunity_score !== null"
            color="primary"
            outline
            data-test="portfolio-score"
          >
            {{ lot.opportunity_score }}
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Opportunity score from last night's screen. Open the lot for the read computed now.
            </q-tooltip>
          </q-badge>
        </div>
      </div>

      <div v-if="moreCount > 0" class="text-caption lot-text-faint q-mt-xs">
        + {{ moreCount }} more parcel{{ moreCount === 1 ? '' : 's' }} held by this owner.
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
  margin-bottom: 6px;
}
.owner-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--lot-ink);
}
.sole-note {
  font-size: 12px;
  line-height: 1.45;
  color: var(--lot-muted);
  margin-top: 4px;
}
.trace-card {
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
}
.trace-line {
  font-size: 13px;
  font-weight: 500;
  color: var(--lot-ink);
}
.trace-note {
  font-size: 10.5px;
  color: var(--lot-faint);
  margin-top: 4px;
}
.stat {
  text-align: center;
  border-radius: var(--lot-radius-sm);
  padding: 6px 4px;
  background: var(--lot-surface-2);
}
.stat-label {
  font-size: 11px;
  color: var(--lot-faint);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
}
.owner-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 260px;
  overflow-y: auto;
}
.owner-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
  cursor: pointer;
  transition: background 0.12s ease;
}
.owner-row:hover {
  background: var(--lot-surface-2);
}
.owner-body {
  min-width: 0;
  flex: 1;
}
.owner-addr {
  font-weight: 600;
  font-size: 13px;
  color: var(--lot-ink);
}
.owner-meta {
  font-size: 11.5px;
  color: var(--lot-muted);
}
</style>
