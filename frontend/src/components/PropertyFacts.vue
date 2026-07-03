<script setup lang="ts">
import { computed } from 'vue'

import { formatCurrency, formatSqft, formatFeet } from '@/lib/format'
import type { ParcelDetail } from '@/lib/types'

const props = defineProps<{ detail: ParcelDetail }>()

const exemptTotal = computed(
  () => (props.detail.exempt_land ?? 0) + (props.detail.exempt_building ?? 0),
)
const hasExemption = computed(() => exemptTotal.value > 0)
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="home_work" size="18px" class="q-mr-xs" />Property
      </div>
      <q-list dense>
        <q-item class="q-px-none">
          <q-item-section>Owner</q-item-section>
          <q-item-section side class="value">{{ detail.owner ?? '—' }}</q-item-section>
        </q-item>
        <q-item v-if="detail.land_use" class="q-px-none">
          <q-item-section>Land use</q-item-section>
          <q-item-section side class="value">{{ detail.land_use }}</q-item-section>
        </q-item>
        <q-item class="q-px-none">
          <q-item-section>Lot area</q-item-section>
          <q-item-section side class="value">{{ formatSqft(detail.lot_area_sqft) }}</q-item-section>
        </q-item>
        <q-item v-if="detail.frontage_ft || detail.depth_ft" class="q-px-none">
          <q-item-section>Frontage × depth</q-item-section>
          <q-item-section side class="value">
            {{ formatFeet(detail.frontage_ft) }} × {{ formatFeet(detail.depth_ft) }}
          </q-item-section>
        </q-item>
        <q-item class="q-px-none">
          <q-item-section>
            Assessed value
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              The OPA's assessed value — the basis for property taxes. Not the same as the market
              estimate in the verdict above.
            </q-tooltip>
          </q-item-section>
          <q-item-section side class="value">{{ formatCurrency(detail.market_value) }}</q-item-section>
        </q-item>
        <q-item v-if="detail.land_value != null" class="q-px-none">
          <q-item-section>
            Land / improvement
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              How the assessment splits between land and any structure. Vacant lots are mostly or
              entirely land value.
            </q-tooltip>
          </q-item-section>
          <q-item-section side class="value">
            {{ formatCurrency(detail.land_value) }} / {{ formatCurrency(detail.improvement_value) }}
          </q-item-section>
        </q-item>
        <q-item v-if="hasExemption" class="q-px-none">
          <q-item-section>
            Tax exemption
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              An OPA exemption is recorded (possible active abatement). Confirm the remaining
              abatement term with OPA — informational, not tax advice.
            </q-tooltip>
          </q-item-section>
          <q-item-section side class="value">{{ formatCurrency(exemptTotal) }}</q-item-section>
        </q-item>
      </q-list>
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
  margin-bottom: 4px;
}
.value {
  font-weight: 500;
  color: var(--lot-ink);
  text-align: right;
  white-space: normal;
  max-width: 60%;
}
</style>
