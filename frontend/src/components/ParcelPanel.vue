<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import AskBox from '@/components/AskBox.vue'
import AssemblagePanel from '@/components/AssemblagePanel.vue'
import ChecklistPanel from '@/components/ChecklistPanel.vue'
import DealPanel from '@/components/DealPanel.vue'
import DistressPanel from '@/components/DistressPanel.vue'
import OwnerPortfolioPanel from '@/components/OwnerPortfolioPanel.vue'
import PropertyFacts from '@/components/PropertyFacts.vue'
import VerdictPanel from '@/components/VerdictPanel.vue'
import { ApiError, api } from '@/lib/api'
import { MAX_COMPARE, useCompareStore } from '@/stores/compare'
import { useParcelStore } from '@/stores/parcel'
import { STAGES, usePipelineStore } from '@/stores/pipeline'
import { useWatchlistStore } from '@/stores/watchlist'

const store = useParcelStore()
const { detail, verdict, loading, error, errorStatus } = storeToRefs(store)
const watchlist = useWatchlistStore()
const pipeline = usePipelineStore()
const compare = useCompareStore()
const $q = useQuasar()
const saving = ref(false)
const addingDeal = ref(false)
const downloadingDossier = ref(false)

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
  <div class="panel-root lot-scroll">
    <q-inner-loading :showing="loading" color="primary" />

    <template v-if="detail">
      <div class="panel-header">
        <q-btn
          round
          unelevated
          :color="isSaved ? 'amber-7' : 'white'"
          :text-color="isSaved ? 'white' : 'primary'"
          :icon="isSaved ? 'bookmark' : 'bookmark_border'"
          size="sm"
          class="save-btn"
          :loading="saving"
          :aria-label="isSaved ? 'Remove from watchlist' : 'Save to watchlist'"
          @click="toggleSave"
        >
          <q-tooltip>{{ isSaved ? 'Saved — click to remove' : 'Save to watchlist' }}</q-tooltip>
        </q-btn>
        <div class="text-h6 ellipsis-2">{{ detail.address ?? detail.parcel_number }}</div>
        <div class="text-caption text-grey-3">Parcel {{ detail.parcel_number }}</div>
        <div class="q-gutter-xs q-mt-sm">
          <q-chip dense color="white" text-color="primary" class="text-weight-bold">
            {{ detail.base_zoning_code ?? 'No zoning' }}
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Base Title 14 zoning district. It sets what you can build by-right — uses, units,
              height, and setbacks.
            </q-tooltip>
          </q-chip>
          <q-chip v-if="detail.is_vacant" dense color="amber-8" text-color="white" icon="grass">
            Vacant
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Flagged by the city's Vacant Property Indicators model as a likely-vacant lot —
              LotScope's core inventory.
            </q-tooltip>
          </q-chip>
          <q-chip
            v-if="detail.is_city_owned"
            dense
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
        </div>
      </div>

      <div class="panel-body q-pa-md q-gutter-md">
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>

        <div class="row items-center justify-center q-gutter-sm">
          <q-btn
            v-if="!currentDeal"
            outline
            no-caps
            color="primary"
            icon="add_task"
            label="Add to pipeline"
            :loading="addingDeal"
            @click="addToPipeline"
          />
          <q-btn
            v-else
            flat
            no-caps
            color="primary"
            icon="view_kanban"
            :label="`In pipeline · ${dealStageLabel}`"
            :to="{ name: 'pipeline' }"
          />
          <q-btn
            outline
            no-caps
            color="grey-8"
            icon="picture_as_pdf"
            label="PDF dossier"
            :loading="downloadingDossier"
            @click="downloadDossier"
          />
          <q-btn
            :outline="!inCompare"
            :unelevated="inCompare"
            no-caps
            :color="inCompare ? 'primary' : 'grey-8'"
            icon="compare_arrows"
            :label="inCompare ? 'In compare' : 'Compare'"
            @click="toggleCompare"
          />
        </div>

        <template v-if="verdict">
          <VerdictPanel :verdict="verdict" />
        </template>
        <q-banner v-else-if="!loading" dense class="bg-grey-2 rounded-borders">
          <template #avatar><q-icon name="info" color="grey-7" /></template>
          No verdict yet.
          <template #action>
            <q-btn flat dense color="primary" label="Compute" @click="store.refreshVerdict()" />
          </template>
        </q-banner>

        <ChecklistPanel />

        <DealPanel />

        <AssemblagePanel />

        <OwnerPortfolioPanel />

        <DistressPanel />

        <PropertyFacts :detail="detail" />

        <div class="text-center">
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

        <AskBox :parcel-number="detail.parcel_number" />
      </div>
    </template>

    <div v-else-if="error && !loading" class="empty-state">
      <q-icon
        :name="errorStatus === 429 ? 'lock_clock' : 'error_outline'"
        size="52px"
        :color="errorStatus === 429 ? 'amber-7' : 'grey-5'"
      />
      <div class="text-subtitle1 text-grey-8 q-mt-md">
        {{ errorStatus === 429 ? 'Daily parcel limit reached' : 'Could not load parcel' }}
      </div>
      <div class="text-body2 text-grey-7 q-mt-xs">{{ error }}</div>
      <q-btn
        v-if="errorStatus === 429"
        class="q-mt-md"
        unelevated
        no-caps
        color="primary"
        icon="workspace_premium"
        label="View account & plans"
        :to="{ name: 'account' }"
      />
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
  overflow-y: auto;
}
.panel-header {
  background: linear-gradient(135deg, #0f4ba8 0%, #1976d2 100%);
  color: white;
  padding: 18px 16px;
  box-shadow: 0 2px 10px rgba(13, 71, 161, 0.25);
  position: relative;
  z-index: 1;
}
.panel-body {
  background: var(--lot-bg);
  padding-bottom: 36px;
  min-height: 100%;
}
.save-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
}
.panel-header .text-h6 {
  padding-right: 44px;
}
.ellipsis-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.25;
}
.empty-state {
  text-align: center;
  padding: 48px 28px;
}
</style>
