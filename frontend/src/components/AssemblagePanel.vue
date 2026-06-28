<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatSqft } from '@/lib/format'
import type { Acquirability, AssemblagePotential } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { assemblage, assemblageLoading } = storeToRefs(store)

interface Badge {
  label: string
  color: string
  icon: string
}

const ACQUIRABILITY: Record<Acquirability, Badge> = {
  same_owner: { label: 'Same owner', color: 'purple-6', icon: 'group' },
  city_owned: { label: 'City / Land Bank', color: 'deep-orange-7', icon: 'account_balance' },
  vacant: { label: 'Vacant', color: 'teal-7', icon: 'grass' },
  built: { label: 'Built', color: 'blue-grey-5', icon: 'home' },
}

const POTENTIAL: Record<AssemblagePotential, Badge> = {
  high: { label: 'Strong assemblage potential', color: 'positive', icon: 'hub' },
  medium: { label: 'Some assemblage potential', color: 'warning', icon: 'hub' },
  low: { label: 'Limited assemblage potential', color: 'grey-6', icon: 'hub' },
  none: { label: 'No easy assemblage', color: 'grey-6', icon: 'block' },
}

const potentialBadge = computed(() =>
  assemblage.value ? POTENTIAL[assemblage.value.potential] : POTENTIAL.none,
)

const unitUnlock = computed(() => {
  const s = assemblage.value?.summary
  if (!s || s.by_right_units_current == null || s.by_right_units_combined == null) return null
  if (s.by_right_units_combined <= s.by_right_units_current) return null
  const estimate = s.units_basis === 'far_estimate'
  return {
    from: s.by_right_units_current,
    to: s.by_right_units_combined,
    added: s.by_right_units_combined - s.by_right_units_current,
    heading: estimate ? 'Estimated capacity' : 'By-right units',
    note: estimate
      ? "A rough capacity from the district's floor-area ratio (assumes ~1,100 sqft of floor area per unit). Confirm with design and the zoning code."
      : 'Confirm the by-right outcome for the combined lot with the zoning code.',
  }
})

function badge(value: Acquirability): Badge {
  return ACQUIRABILITY[value]
}

function selectNeighbor(parcelNumber: string): void {
  void store.select(parcelNumber)
}
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="hub" size="18px" class="q-mr-xs" />Assemblage radar
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          Adjacent lots you might buy to build a larger project. Candidates are neighbors with the
          same zoning that are vacant, city-owned, or share this owner.
        </q-tooltip>
        <q-space />
        <q-spinner v-if="assemblageLoading && !assemblage" color="primary" size="18px" />
      </div>

      <template v-if="assemblage">
        <q-chip
          dense
          square
          :color="potentialBadge.color"
          text-color="white"
          :icon="potentialBadge.icon"
        >
          {{ potentialBadge.label }}
        </q-chip>

        <div v-if="unitUnlock" class="unit-unlock q-mt-sm">
          <q-icon name="apartment" size="20px" class="q-mr-sm" />
          <div>
            <div class="unlock-head">
              {{ unitUnlock.heading }}: <b>{{ unitUnlock.from }} → {{ unitUnlock.to }}</b>
              <span class="unlock-add">+{{ unitUnlock.added }}</span>
            </div>
            <div class="unlock-sub">
              Assembling the buyable neighbors could add about {{ unitUnlock.added }} more unit(s).
              {{ unitUnlock.note }}
            </div>
          </div>
        </div>

        <div v-if="assemblage.summary.candidate_count > 0" class="row q-col-gutter-sm q-mt-xs">
          <div class="col-6 stat">
            <div class="stat-label">Buyable neighbors</div>
            <div class="stat-value">{{ assemblage.summary.candidate_count }}</div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Adjacent same-zoning lots that are vacant, city-owned, or share this owner.
            </q-tooltip>
          </div>
          <div class="col-6 stat">
            <div class="stat-label">Combined land</div>
            <div class="stat-value">{{ formatSqft(assemblage.summary.combined_lot_area_sqft) }}</div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              This lot plus all buyable same-zoning neighbors. Approximate; confirm by-right
              outcomes for the combined parcel.
            </q-tooltip>
          </div>
        </div>

        <div v-if="assemblage.neighbors.length" class="neighbor-list q-mt-sm">
          <div
            v-for="lot in assemblage.neighbors"
            :key="lot.parcel_number"
            class="neighbor"
            :class="{ candidate: lot.is_candidate }"
            @click="selectNeighbor(lot.parcel_number)"
          >
            <q-icon :name="badge(lot.acquirability).icon" :color="badge(lot.acquirability).color" size="18px" />
            <div class="neighbor-body">
              <div class="neighbor-title ellipsis">
                {{ lot.address ?? lot.parcel_number }}
              </div>
              <div class="neighbor-meta">
                {{ lot.base_zoning_code ?? 'No zoning' }} ·
                {{ formatSqft(lot.lot_area_sqft) }}
                <span v-if="!lot.same_zoning" class="text-grey-6">· different zoning</span>
              </div>
            </div>
            <q-badge
              :color="badge(lot.acquirability).color"
              text-color="white"
              class="neighbor-badge"
            >
              {{ badge(lot.acquirability).label }}
            </q-badge>
          </div>
        </div>
        <div v-else class="text-body2 text-grey-6 q-mt-sm">
          No adjacent parcels detected for this lot.
        </div>

        <ul v-if="assemblage.reasons.length" class="reasons">
          <li v-for="reason in assemblage.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </template>

      <div v-else-if="assemblageLoading" class="text-body2 text-grey-6">Scanning adjacent lots…</div>
      <div v-else class="text-body2 text-grey-6">Adjacent-lot data is unavailable.</div>
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
  color: #5b6b7d;
  margin-bottom: 6px;
}
.stat {
  text-align: center;
  border-radius: var(--lot-radius-sm);
  padding: 6px 4px;
  background: #f6f8fb;
}
.stat-label {
  font-size: 11px;
  color: #78909c;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: #1f2933;
}
.unit-unlock {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: var(--lot-radius-sm);
  background: linear-gradient(135deg, #e8f5e9, #f1f8e9);
  border: 1px solid #c5e1a5;
  color: #2e5e1e;
}
.unlock-head {
  font-size: 14px;
}
.unlock-head b {
  color: #2e7d32;
}
.unlock-add {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 8px;
  background: #2e7d32;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}
.unlock-sub {
  font-size: 11.5px;
  color: #5b6b5b;
  line-height: 1.35;
  margin-top: 2px;
}
.neighbor-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.neighbor {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: #f8fafc;
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 0.12s ease;
}
.neighbor:hover {
  background: #eef2f7;
}
.neighbor.candidate {
  border-left-color: #7b1fa2;
}
.neighbor-body {
  min-width: 0;
  flex: 1;
}
.neighbor-title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2933;
}
.neighbor-meta {
  font-size: 11.5px;
  color: #5b6b7d;
}
.neighbor-badge {
  flex-shrink: 0;
  font-size: 10px;
}
.reasons {
  margin: 10px 0 0;
  padding-left: 18px;
}
.reasons li {
  font-size: 12px;
  color: #5b6b7d;
  line-height: 1.4;
  margin-bottom: 3px;
}
</style>
