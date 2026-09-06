<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import AssemblagePanel from '@/components/AssemblagePanel.vue'
import ChecklistPanel from '@/components/ChecklistPanel.vue'
import DevelopmentProgramPanel from '@/components/DevelopmentProgramPanel.vue'
import CompsPanel from '@/components/CompsPanel.vue'
import DealCard from '@/components/DealCard.vue'
import DeedRestrictionsPanel from '@/components/DeedRestrictionsPanel.vue'
import DistressPanel from '@/components/DistressPanel.vue'
import DeedsEvidence from '@/components/DeedsEvidence.vue'
import DelinquencyEvidence from '@/components/DelinquencyEvidence.vue'
import FreshnessPanel from '@/components/FreshnessPanel.vue'
import ReportCorrectionDialog from '@/components/ReportCorrectionDialog.vue'
import HistoricPanel from '@/components/HistoricPanel.vue'
import OwnerPortfolioPanel from '@/components/OwnerPortfolioPanel.vue'
import LotSectionNav from '@/components/LotSectionNav.vue'
import RiskPanel from '@/components/RiskPanel.vue'
import SheriffEvidence from '@/components/SheriffEvidence.vue'
import ViolationsEvidence from '@/components/ViolationsEvidence.vue'
import VerdictSection from '@/components/VerdictSection.vue'
import type { LotSection } from '@/lib/sourceLinks'
import PropertyFacts from '@/components/PropertyFacts.vue'
import ScenariosPanel from '@/components/ScenariosPanel.vue'
import SnapshotPanel from '@/components/SnapshotPanel.vue'
import OverlayPanel from '@/components/OverlayPanel.vue'
import SubdivisionPanel from '@/components/SubdivisionPanel.vue'
import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { DistressTier } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'
import { STAGES, usePipelineStore } from '@/stores/pipeline'
import { useWatchlistStore } from '@/stores/watchlist'

const store = useParcelStore()
const { detail, verdict, envelope, checklist, nextSheriffSale, loading, error, errorStatus } =
  storeToRefs(store)
const watchlist = useWatchlistStore()
const pipeline = usePipelineStore()

const props = withDefaults(defineProps<{ showBack?: boolean }>(), { showBack: false })
const emit = defineEmits<{ back: [] }>()
const $q = useQuasar()
const saving = ref(false)
const correctionOpen = ref(false)
const addingDeal = ref(false)
const downloadingDossier = ref(false)
function scrollTo(id: LotSection): void {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Every section is on the page for every lot. "No sheriff-sale listing is on file" is an
// answer a buyer needs, and a nav entry that appears on some lots and not others is a
// section a reader stops looking for.
const visibleSections: { id: LotSection; label: string }[] = [
  { id: 'verdict', label: 'Verdict' },
  { id: 'sheriff', label: 'Sheriff' },
  { id: 'deeds', label: 'Deeds' },
  { id: 'violations', label: 'Violations' },
  { id: 'delinquency', label: 'Delinquency' },
  { id: 'comps', label: 'Comps' },
  { id: 'zoning-overlays', label: 'Zoning' },
  { id: 'neighbors', label: 'Neighbours' },
  { id: 'corrections', label: 'Corrections' },
]

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

const MOTIVATION_CHIP: Partial<
  Record<DistressTier, { label: string; color: string; icon: string }>
> = {
  high: { label: 'High seller motivation', color: 'negative', icon: 'local_fire_department' },
  medium: { label: 'Some seller motivation', color: 'warning', icon: 'trending_up' },
}

const motivation = computed(() => {
  const result = store.distress
  if (!result) return null
  const style = MOTIVATION_CHIP[result.tier]
  return style ? { ...style, score: result.score } : null
})

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
        <div class="action-row">
          <q-btn
            v-if="props.showBack"
            flat
            dense
            round
            icon="chevron_left"
            aria-label="Back"
            class="back-btn"
            data-test="dossier-back"
            @click="emit('back')"
          />
          <q-space />
          <div class="header-actions">
            <q-btn
              class="act"
              :class="{ 'act-on': isSaved }"
              flat
              dense
              no-caps
              size="sm"
              :icon="isSaved ? 'bookmark' : 'bookmark_border'"
              :label="isSaved ? 'Saved' : 'Save'"
              :loading="saving"
              :aria-label="isSaved ? 'Remove from watchlist' : 'Save to watchlist'"
              data-test="parcel-action-save"
              @click="toggleSave"
            />
            <q-btn
              v-if="!currentDeal"
              class="act"
              flat
              dense
              no-caps
              size="sm"
              icon="add_task"
              label="Pipeline"
              :loading="addingDeal"
              data-test="parcel-action-pipeline"
              @click="addToPipeline"
            />
            <q-btn
              v-else
              class="act act-on"
              flat
              dense
              no-caps
              size="sm"
              icon="view_kanban"
              :label="dealStageLabel"
              data-test="parcel-action-pipeline"
              :to="{ name: 'deals' }"
            />
            <q-btn
              class="act"
              flat
              dense
              no-caps
              size="sm"
              icon="forum"
              label="Ask the Analyst"
              aria-label="Ask the Analyst about this lot"
              data-test="parcel-action-ask"
              :to="{
                name: 'analyst',
                query: {
                  about: detail.parcel_number,
                  label: detail.address ?? detail.parcel_number,
                },
              }"
            />
            <q-btn
              class="act"
              flat
              dense
              no-caps
              size="sm"
              icon="fact_check"
              label="Diligence $199"
              aria-label="Lot diligence, not available yet"
              disable
              data-test="parcel-action-diligence"
            >
              <q-tooltip>Lot Diligence arrives in Phase 5.</q-tooltip>
            </q-btn>
            <q-btn
              class="act"
              flat
              dense
              no-caps
              size="sm"
              icon="picture_as_pdf"
              label="Report"
              :loading="downloadingDossier"
              aria-label="Download PDF dossier"
              data-test="parcel-action-report"
              @click="downloadDossier"
            />
          </div>
        </div>

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

        <div class="chips">
          <q-chip dense square color="primary" text-color="white" class="text-weight-medium">
            {{ detail.resolved_zoning_code ?? detail.base_zoning_code ?? 'No zoning' }}
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Zoning district. It sets what you can build by-right — uses, units, height, and
              setbacks.<template v-if="detail.zoning_resolution === 'spatial'">
                Resolved from the zoning map (no per-parcel attribute on file).</template
              >
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
                treat this as low confidence.</template
              >
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
          <q-chip
            v-if="motivation"
            dense
            square
            clickable
            :color="motivation.color"
            text-color="white"
            :icon="motivation.icon"
            data-test="motivation-chip"
            @click="scrollTo('verdict')"
          >
            {{ motivation.label }} · {{ motivation.score }}/100
            <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
              A distress index from tax delinquency, sheriff sale, liens, L&amp;I, vacancy, and
              absentee ownership, scored against the signals this market publishes. Higher means the
              owner is more likely to sell. Open the Verdict tab for the contributing factors.
            </q-tooltip>
          </q-chip>
        </div>
      </header>

      <div class="panel-body lot-scroll">
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>

        <LotSectionNav :sections="visibleSections" />

        <div class="lot-sections">
          <section id="verdict" class="lot-section" data-test="lot-section-verdict-wrap">
            <q-banner v-if="isDeveloped" dense class="developed-banner rounded-borders">
              <template #avatar><q-icon name="home_work" color="blue-grey-6" /></template>
              <div class="developed-head">Already developed — {{ developedUse }}</div>
              <div class="developed-note">{{ developedNote }}</div>
            </q-banner>
            <VerdictSection
              v-if="verdict"
              :verdict="verdict"
              :developed="isDeveloped"
              :checklist="checklist"
              :cited-section="envelope?.cited_section ?? null"
            />
            <q-banner v-else-if="!loading" dense class="bg-grey-2 rounded-borders">
              <template #avatar><q-icon name="info" color="grey-7" /></template>
              No verdict yet.
              <template #action>
                <q-btn flat dense color="primary" label="Compute" @click="store.refreshVerdict()" />
              </template>
            </q-banner>
            <SnapshotPanel :parcel-number="detail.parcel_number" />
            <DevelopmentProgramPanel />
            <RiskPanel />
            <DistressPanel />
            <DealCard />
            <ScenariosPanel />
            <ChecklistPanel />
          </section>

          <section id="sheriff" class="lot-section" data-test="lot-section-sheriff">
            <h2 class="lot-section__title">Sheriff listing</h2>
            <SheriffEvidence :parcel-number="detail.parcel_number" />
          </section>

          <section id="deeds" class="lot-section" data-test="lot-section-deeds">
            <h2 class="lot-section__title">Deeds</h2>
            <DeedsEvidence :parcel-number="detail.parcel_number" />
            <DeedRestrictionsPanel />
          </section>

          <section id="violations" class="lot-section" data-test="lot-section-violations">
            <h2 class="lot-section__title">Violations</h2>
            <ViolationsEvidence :parcel-number="detail.parcel_number" />
          </section>

          <section id="delinquency" class="lot-section" data-test="lot-section-delinquency">
            <h2 class="lot-section__title">Delinquency</h2>
            <DelinquencyEvidence :parcel-number="detail.parcel_number" />
          </section>

          <section id="comps" class="lot-section" data-test="lot-section-comps">
            <h2 class="lot-section__title">Comps</h2>
            <CompsPanel />
          </section>

          <section id="zoning-overlays" class="lot-section" data-test="lot-section-zoning">
            <h2 class="lot-section__title">Zoning and overlays</h2>
            <SubdivisionPanel />
            <OverlayPanel />
            <HistoricPanel />
            <PropertyFacts :detail="detail" />
          </section>

          <section id="neighbors" class="lot-section" data-test="lot-section-neighbors">
            <h2 class="lot-section__title">Neighbours</h2>
            <AssemblagePanel />
            <OwnerPortfolioPanel />
          </section>

          <section id="corrections" class="lot-section" data-test="lot-section-corrections">
            <h2 class="lot-section__title">Corrections</h2>
            <div class="correction-cta">
              <q-btn
                flat
                dense
                no-caps
                color="grey-7"
                icon="flag"
                label="Report incorrect data"
                data-test="report-correction"
                @click="correctionOpen = true"
              />
            </div>
            <ReportCorrectionDialog
              v-model="correctionOpen"
              :parcel-number="detail.parcel_number"
            />
            <FreshnessPanel :parcel-number="detail.parcel_number" />
          </section>
        </div>
      </div>
    </template>

    <div v-else-if="error && errorStatus === 429 && !loading" class="empty-state"></div>

    <div v-else-if="error && !loading" class="empty-state">
      <q-icon name="error_outline" size="52px" color="grey-5" />
      <div class="text-subtitle1 lot-text-ink q-mt-md">Could not load parcel</div>
      <div class="text-body2 lot-text-muted q-mt-xs">{{ error }}</div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <q-icon name="travel_explore" size="56px" color="grey-4" />
      <div class="text-subtitle1 lot-text-ink q-mt-md">Find a parcel</div>
      <div class="text-body2 lot-text-muted">
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
  padding: 6px 14px 10px;
  z-index: 2;
}
.action-row {
  display: flex;
  align-items: center;
  gap: 2px;
}
.back-btn {
  color: var(--lot-muted);
  flex: none;
}
.header-id {
  min-width: 0;
  flex: 1;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 0 0 auto;
}
.act {
  color: var(--lot-muted);
  border-radius: var(--lot-radius-sm);
  padding: 4px 8px;
  min-height: 44px;
}
.act.act-on {
  color: var(--lot-accent-ink, var(--lot-accent));
  background: var(--lot-accent-soft);
}
@media (max-width: 720px) {
  .header-actions {
    flex: 1 1 auto;
    gap: 0;
  }
  .act {
    flex: 1 1 0;
    padding: 4px 2px;
  }
  .act :deep(.q-btn__content) {
    flex-direction: column;
    gap: 1px;
    font-size: 10.5px;
  }
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
  /* No padding at the top: the section nav sticks to the scrollport, and a padded edge
     leaves a band above it that the page scrolls through in plain sight. */
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lot-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.lot-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  /* The section nav is sticky, so an anchored jump has to stop short of it or the
     heading it lands on sits underneath. */
  scroll-margin-top: 60px;
}
.lot-section__title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin: 0;
}
.correction-cta {
  display: flex;
  justify-content: center;
  padding-top: 4px;
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
