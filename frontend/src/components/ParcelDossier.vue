<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import AskBox from '@/components/AskBox.vue'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import RepositoryBadge from '@/components/RepositoryBadge.vue'
import AssemblagePanel from '@/components/AssemblagePanel.vue'
import AssessmentPanel from '@/components/AssessmentPanel.vue'
import ChecklistPanel from '@/components/ChecklistPanel.vue'
import CompsPanel from '@/components/CompsPanel.vue'
import DealPanel from '@/components/DealPanel.vue'
import DeedRestrictionsPanel from '@/components/DeedRestrictionsPanel.vue'
import ReportPanel from '@/components/ReportPanel.vue'
import DistressPanel from '@/components/DistressPanel.vue'
import HistoricPanel from '@/components/HistoricPanel.vue'
import MarketContextPanel from '@/components/MarketContextPanel.vue'
import BuyersNearbyPanel from '@/components/BuyersNearbyPanel.vue'
import OwnerPortfolioPanel from '@/components/OwnerPortfolioPanel.vue'
import PropertyFacts from '@/components/PropertyFacts.vue'
import ScenariosPanel from '@/components/ScenariosPanel.vue'
import SnapshotPanel from '@/components/SnapshotPanel.vue'
import SubdivisionPanel from '@/components/SubdivisionPanel.vue'
import VerdictHero from '@/components/VerdictHero.vue'
import VerdictPanel from '@/components/VerdictPanel.vue'
import WhyScoreDrawer from '@/components/WhyScoreDrawer.vue'
import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import { MAX_COMPARE, useCompareStore } from '@/stores/compare'
import { useMarketStore } from '@/stores/market'
import { useParcelStore } from '@/stores/parcel'
import { STAGES, usePipelineStore } from '@/stores/pipeline'
import { useWatchlistStore } from '@/stores/watchlist'

const store = useParcelStore()
const { detail, verdict, nextSheriffSale, loading, error, errorStatus } = storeToRefs(store)
const watchlist = useWatchlistStore()
const pipeline = usePipelineStore()
const compare = useCompareStore()
const market = useMarketStore()
const $q = useQuasar()
const saving = ref(false)
const whyOpen = ref(false)
const addingDeal = ref(false)
const downloadingDossier = ref(false)
const tab = ref('verdict')

const TABS = [
  { name: 'verdict', label: 'Verdict', icon: 'verified' },
  { name: 'deal', label: 'Deal', icon: 'payments' },
  { name: 'land', label: 'Land', icon: 'architecture' },
  { name: 'risk', label: 'Risk', icon: 'gpp_maybe' },
  { name: 'docs', label: 'Docs', icon: 'description' },
]

const tabsAlign = computed(() => ($q.screen.lt.md ? 'left' : 'justify'))

const sheriffCountdown = computed(() => {
  const sale = nextSheriffSale.value
  if (sale === null) return null
  const days = sale.days_until
  const when = days <= 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`
  return {
    label: `Sheriff sale ${when}`,
    color: days <= 30 ? 'red-9' : 'red-6',
    date: sale.sale_date,
    caseNumber: sale.case_number,
  }
})

const LOW_VACANCY_CONFIDENCE = 0.5
const lowVacancyConfidence = computed(() => {
  const confidence = detail.value?.vacancy_confidence
  return confidence != null && confidence < LOW_VACANCY_CONFIDENCE
})

const VACANT_LAND_PREFIX = 'VACANT LAND'
const isVacantLand = computed(() => {
  const d = detail.value
  if (d === null) return false
  return d.is_vacant === true || (d.land_use ?? '').toUpperCase().startsWith(VACANT_LAND_PREFIX)
})
const isDeveloped = computed(() => {
  const d = detail.value
  if (d === null || isVacantLand.value) return false
  return d.land_use !== null && d.land_use.trim() !== ''
})
const developedUse = computed(() => {
  const lu = detail.value?.land_use
  if (lu == null || lu.trim() === '') return ''
  return lu.charAt(0).toUpperCase() + lu.slice(1).toLowerCase()
})
const developedNote = computed(() => {
  const mv = detail.value?.market_value
  const assessed = mv != null ? ` (assessed at ${formatCurrency(mv)})` : ''
  return `LotScope focuses on vacant & infill land. This parcel already has a structure${assessed}, so the buildability, land value, and deal figures below model a hypothetical teardown or redevelopment — not the property's current value.`
})

const dealEmpty = computed(
  () => !store.deal && !store.scenarios && !store.comps && !store.assessment && !store.marketContext,
)
const riskEmpty = computed(() => !store.distress && !store.ownerPortfolio)

async function downloadDossier(): Promise<void> {
  if (detail.value === null || downloadingDossier.value) return
  downloadingDossier.value = true
  try {
    await api.downloadDossier(detail.value.parcel_number)
  } catch (cause) {
    const message = cause instanceof ApiError ? cause.message : 'Could not generate the dossier.'
    $q.notify({ message, color: 'negative', icon: 'error' })
  } finally {
    downloadingDossier.value = false
  }
}

const currentDeal = computed(() =>
  detail.value ? pipeline.dealFor(detail.value.parcel_number) : undefined,
)
const dealStageLabel = computed(
  () => STAGES.find((stage) => stage.value === currentDeal.value?.stage)?.label ?? '',
)

async function addToPipeline(): Promise<void> {
  if (detail.value === null || addingDeal.value) return
  addingDeal.value = true
  try {
    await pipeline.add(detail.value.parcel_number)
    $q.notify({ message: 'Added to your pipeline', color: 'positive', icon: 'view_kanban' })
  } catch (cause) {
    const message =
      cause instanceof ApiError && cause.status === 429
        ? cause.message
        : 'Could not add to pipeline.'
    $q.notify({ message, color: 'negative', icon: 'error' })
  } finally {
    addingDeal.value = false
  }
}

const isSaved = computed(() =>
  detail.value ? watchlist.isSaved(detail.value.parcel_number) : false,
)

const inCompare = computed(() =>
  detail.value ? compare.has(detail.value.parcel_number) : false,
)

function toggleCompare(): void {
  if (detail.value === null) return
  if (inCompare.value) {
    compare.remove(detail.value.parcel_number)
    $q.notify({ message: 'Removed from compare', color: 'grey-8', icon: 'compare_arrows' })
    return
  }
  if (compare.add(detail.value.parcel_number)) {
    $q.notify({ message: 'Added to compare', color: 'positive', icon: 'compare_arrows' })
  } else {
    $q.notify({
      message: `Compare holds up to ${MAX_COMPARE} lots`,
      color: 'warning',
      icon: 'info',
    })
  }
}

onMounted(() => {
  void watchlist.ensureLoaded()
  void pipeline.ensureLoaded()
})

async function toggleSave(): Promise<void> {
  if (detail.value === null || saving.value) return
  const parcelNumber = detail.value.parcel_number
  saving.value = true
  try {
    if (watchlist.isSaved(parcelNumber)) {
      await watchlist.remove(parcelNumber)
      $q.notify({ message: 'Removed from watchlist', color: 'grey-8', icon: 'bookmark_remove' })
    } else {
      await watchlist.add(parcelNumber)
      $q.notify({ message: 'Saved to watchlist', color: 'positive', icon: 'bookmark_added' })
    }
  } catch (cause) {
    const message =
      cause instanceof ApiError && cause.status === 429
        ? cause.message
        : 'Could not update your watchlist.'
    $q.notify({ message, color: 'negative', icon: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="panel-root">
    <q-inner-loading :showing="loading" color="primary" />

    <template v-if="detail">
      <header class="panel-header">
        <div class="header-row">
          <div class="header-id">
            <div
              class="addr ellipsis-2"
              role="button"
              tabindex="0"
              @click="store.focusOnMap()"
              @keyup.enter="store.focusOnMap()"
            >
              {{ detail.address ?? detail.parcel_number }}
              <q-tooltip anchor="bottom left" self="top left">Show on map</q-tooltip>
            </div>
            <div class="pid lot-numeric">Parcel {{ detail.local_key ?? detail.parcel_number }}</div>
          </div>
          <div class="header-actions">
            <q-btn
              v-if="!currentDeal"
              outline
              dense
              no-caps
              size="sm"
              color="primary"
              icon="add_task"
              label="Pipeline"
              :loading="addingDeal"
              @click="addToPipeline"
            />
            <q-btn
              v-else
              flat
              dense
              no-caps
              size="sm"
              color="primary"
              icon="view_kanban"
              :label="dealStageLabel"
              :to="{ name: 'pipeline', params: { market: market.active } }"
            />
            <q-btn
              flat
              dense
              round
              size="sm"
              :color="inCompare ? 'primary' : 'grey-8'"
              icon="compare_arrows"
              :aria-label="inCompare ? 'In compare' : 'Add to compare'"
              @click="toggleCompare"
            >
              <q-tooltip>{{ inCompare ? 'In compare — click to remove' : 'Add to compare' }}</q-tooltip>
            </q-btn>
            <q-btn
              flat
              dense
              round
              size="sm"
              color="grey-8"
              icon="picture_as_pdf"
              :loading="downloadingDossier"
              aria-label="Download PDF dossier"
              @click="downloadDossier"
            >
              <q-tooltip>Download PDF dossier</q-tooltip>
            </q-btn>
            <q-btn
              round
              unelevated
              :color="isSaved ? 'amber-7' : 'grey-3'"
              :text-color="isSaved ? 'white' : 'grey-8'"
              :icon="isSaved ? 'bookmark' : 'bookmark_border'"
              size="sm"
              :loading="saving"
              :aria-label="isSaved ? 'Remove from watchlist' : 'Save to watchlist'"
              @click="toggleSave"
            >
              <q-tooltip>{{ isSaved ? 'Saved — click to remove' : 'Save to watchlist' }}</q-tooltip>
            </q-btn>
          </div>
        </div>
        <div class="chips">
          <q-chip dense square color="primary" text-color="white" class="text-weight-medium">
            {{ detail.resolved_zoning_code ?? detail.base_zoning_code ?? 'No zoning' }}
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Zoning district. It sets what you can build by-right — uses, units, height, and
              setbacks.<template v-if="detail.zoning_resolution === 'spatial'">
                Resolved from the zoning map (no per-parcel attribute on file).</template>
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="detail.is_vacant"
            dense
            square
            :color="lowVacancyConfidence ? 'amber-6' : 'amber-8'"
            text-color="white"
            icon="grass"
          >
            Vacant<span v-if="lowVacancyConfidence" class="q-ml-xs">· low confidence</span>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Flagged by the city's Vacant Property Indicators model as a likely-vacant lot —
              LotScope's core inventory.<template v-if="lowVacancyConfidence">
                Corroborating signals are weak (e.g. a recent permit or an assessed structure), so
                treat this as low confidence.</template>
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="detail.condemned_status"
            dense
            square
            color="deep-orange-8"
            text-color="white"
            icon="report"
          >
            Condemned / dead-end
            <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
              On the city's Condemned &amp; Dead-End Properties list (PLI). "Dead-end" means the
              city cannot locate the owner. An unscored fact for now — it does not affect the risk
              score at this version. Known only for listed parcels, not citywide.
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="isDeveloped"
            dense
            square
            color="blue-grey-6"
            text-color="white"
            icon="home_work"
          >
            Developed
            <q-tooltip max-width="250px" anchor="top middle" self="bottom middle">
              Already developed ({{ developedUse }}). LotScope focuses on vacant &amp; infill land —
              the buildability and land-value figures describe a hypothetical redevelopment, not the
              current improved property.
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="detail.is_city_owned"
            dense
            square
            color="deep-orange"
            text-color="white"
            icon="account_balance"
          >
            City-owned
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Owned by the City or Land Bank. Acquisition runs through the public disposition
              process, not a private sale.
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="sheriffCountdown"
            dense
            square
            :color="sheriffCountdown.color"
            text-color="white"
            icon="gavel"
          >
            {{ sheriffCountdown.label }}
            <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
              Scheduled for a Sheriff sale on {{ sheriffCountdown.date }} (case
              {{ sheriffCountdown.caseNumber }}). A hard deadline the owner is racing — often the
              strongest motivated-seller signal.
            </q-tooltip>
          </q-chip>
        </div>
        <RepositoryBadge :parcel-number="detail.parcel_number" />
      </header>

      <q-tabs
        v-model="tab"
        dense
        no-caps
        class="dossier-tabs"
        active-color="primary"
        indicator-color="primary"
        :align="tabsAlign"
        narrow-indicator
      >
        <q-tab v-for="t in TABS" :key="t.name" :name="t.name" :icon="t.icon" :label="t.label" />
      </q-tabs>

      <div class="panel-body lot-scroll">
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>

        <q-tab-panels v-model="tab" animated keep-alive class="dossier-panels">
          <q-tab-panel name="verdict" class="tab-pane">
            <q-banner v-if="isDeveloped" dense class="developed-banner rounded-borders">
              <template #avatar><q-icon name="home_work" color="blue-grey-6" /></template>
              <div class="developed-head">Already developed — {{ developedUse }}</div>
              <div class="developed-note">{{ developedNote }}</div>
            </q-banner>
            <VerdictHero
              v-if="verdict"
              :verdict="verdict"
              :developed="isDeveloped"
              @explain="whyOpen = true"
            />
            <WhyScoreDrawer v-if="verdict" v-model="whyOpen" :verdict="verdict" />
            <q-banner v-else-if="!loading" dense class="bg-grey-2 rounded-borders">
              <template #avatar><q-icon name="info" color="grey-7" /></template>
              No verdict yet.
              <template #action>
                <q-btn flat dense color="primary" label="Compute" @click="store.refreshVerdict()" />
              </template>
            </q-banner>
            <SnapshotPanel :parcel-number="detail.parcel_number" />
            <VerdictPanel v-if="verdict" :verdict="verdict" :developed="isDeveloped" />
            <ChecklistPanel />
            <div class="tab-foot">
              <q-btn
                flat
                dense
                no-caps
                color="grey-7"
                icon="refresh"
                label="Recompute verdict"
                :loading="loading"
                @click="store.refreshVerdict()"
              />
            </div>
          </q-tab-panel>

          <q-tab-panel name="deal" class="tab-pane">
            <DealPanel />
            <ScenariosPanel />
            <CompsPanel />
            <AssessmentPanel />
            <MarketContextPanel />
            <div v-if="dealEmpty" class="tab-empty">
              <q-icon name="query_stats" size="26px" />
              <span>No deal, comp, or market data for this lot yet.</span>
            </div>
          </q-tab-panel>

          <q-tab-panel name="land" class="tab-pane">
            <SubdivisionPanel />
            <AssemblagePanel />
            <HistoricPanel />
            <PropertyFacts :detail="detail" />
          </q-tab-panel>

          <q-tab-panel name="risk" class="tab-pane">
            <DistressPanel />
            <OwnerPortfolioPanel />
            <BuyersNearbyPanel />
            <div v-if="riskEmpty" class="tab-empty">
              <q-icon name="verified_user" size="26px" />
              <span>No distress signals or owner-portfolio data surfaced for this lot.</span>
            </div>
          </q-tab-panel>

          <q-tab-panel name="docs" class="tab-pane">
            <ReportPanel :parcel-number="detail.parcel_number" />
            <DeedRestrictionsPanel />
            <AskBox :parcel-number="detail.parcel_number" />
          </q-tab-panel>
        </q-tab-panels>
      </div>
    </template>

    <div v-else-if="error && errorStatus === 429 && !loading" class="empty-state">
      <UpgradePrompt cap="parcel_views" variant="card" cta="View account & plans" />
    </div>

    <div v-else-if="error && !loading" class="empty-state">
      <q-icon name="error_outline" size="52px" color="grey-5" />
      <div class="text-subtitle1 text-grey-8 q-mt-md">Could not load parcel</div>
      <div class="text-body2 text-grey-7 q-mt-xs">{{ error }}</div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <q-icon name="travel_explore" size="56px" color="grey-4" />
      <div class="text-subtitle1 text-grey-7 q-mt-md">Find a parcel</div>
      <div class="text-body2 text-grey-6">
        Search by address, owner, or parcel number — or click any lot on the map — to see its
        buildability, value, and risk verdict.
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel-root {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--lot-bg);
}
.panel-header {
  flex: 0 0 auto;
  background: var(--lot-surface);
  border-bottom: 1px solid var(--lot-border);
  padding: 12px 14px 10px;
  z-index: 2;
}
.header-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.header-id {
  min-width: 0;
  flex: 1;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 1px;
  flex: 0 0 auto;
}
.addr {
  font-size: 17px;
  font-weight: 700;
  color: var(--lot-ink);
  line-height: 1.25;
  letter-spacing: -0.01em;
  cursor: pointer;
}
.addr:hover {
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
.pid {
  font-size: 12px;
  color: var(--lot-faint);
  margin-top: 1px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
}
.ellipsis-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dossier-tabs {
  flex: 0 0 auto;
  background: var(--lot-surface);
  border-bottom: 1px solid var(--lot-border);
  padding: 0 8px;
  color: var(--lot-muted);
}
.dossier-panels {
  background: transparent;
}
.tab-pane {
  padding: 4px 0 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tab-foot {
  display: flex;
  justify-content: center;
}
.tab-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  padding: 28px 16px;
  color: var(--lot-faint);
  font-size: 13px;
}
.rounded-borders {
  border-radius: var(--lot-radius);
}
.developed-banner {
  background: var(--lot-surface-2);
  border: 1px solid var(--lot-border);
  border-left: 3px solid #607d8b;
  color: var(--lot-muted);
}
.developed-head {
  font-weight: 700;
  font-size: 13px;
  color: var(--lot-ink);
}
.developed-note {
  font-size: 12px;
  line-height: 1.4;
  margin-top: 2px;
}
.empty-state {
  text-align: center;
  padding: 48px 28px;
  margin: auto;
}
</style>
