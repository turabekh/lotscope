<script setup lang="ts">
import { useQuasar } from 'quasar'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import GenerateOfferDialog from '@/components/GenerateOfferDialog.vue'
import { api, ApiError } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { DealItem, DealStage } from '@/lib/types'
import { STAGES, usePipelineStore } from '@/stores/pipeline'

const $q = useQuasar()
const router = useRouter()
const pipeline = usePipelineStore()
const { deals, loading } = storeToRefs(pipeline)

const selected = ref<Set<string>>(new Set())
const offerFor = ref<DealItem | null>(null)
const busy = ref(false)

const isMobile = computed(() => $q.screen.lt.md)
const anySelected = computed(() => selected.value.size > 0)

onMounted(() => void pipeline.ensureLoaded())

function toggle(parcelNumber: string): void {
  const next = new Set(selected.value)
  if (next.has(parcelNumber)) next.delete(parcelNumber)
  else next.add(parcelNumber)
  selected.value = next
}

async function setStage(deal: DealItem, stage: DealStage): Promise<void> {
  // Saved on change: a dropdown that needs a second confirming click is a dropdown people
  // forget to confirm.
  await pipeline.moveStage(deal.parcel_number, stage)
}

function openLot(deal: DealItem): void {
  void router.push({ name: 'lot', params: { parcelNumber: deal.parcel_number } })
}

/** Hand the selection to the Analyst rather than making the buyer retype the addresses. */
function askAboutSelected(): void {
  const chosen = deals.value.filter((deal) => selected.value.has(deal.parcel_number))
  if (!chosen.length) return
  const label = chosen.map((deal) => deal.address ?? deal.parcel_number).join(', ')
  void router.push({
    name: 'analyst',
    query: { about: chosen.map((deal) => deal.parcel_number).join(','), label },
  })
}

async function exportCsv(): Promise<void> {
  busy.value = true
  try {
    await api.exportPipeline()
  } catch (cause) {
    $q.notify({
      message: cause instanceof ApiError ? cause.message : 'The export failed.',
      color: 'negative',
    })
  } finally {
    busy.value = false
  }
}

function money(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : formatCurrency(value)
}

function noteFor(deal: DealItem): string | null {
  const note = deal.analyst_note?.trim()
  if (!note) return null
  const firstLine = note.split('\n').find((line) => line.trim()) ?? note
  return firstLine.length > 160 ? `${firstLine.slice(0, 160)}…` : firstLine
}
</script>

<template>
  <div class="deals">
    <header class="deals__head">
      <h1 class="deals__title">Deals</h1>
      <q-space />
      <q-btn
        flat
        dense
        no-caps
        icon="download"
        label="Export CSV"
        :loading="busy"
        data-test="deals-export"
        @click="exportCsv"
      />
      <q-btn
        flat
        dense
        no-caps
        icon="forum"
        :label="anySelected ? `Ask about ${selected.size}` : 'Ask the Analyst'"
        :disable="!anySelected"
        data-test="deals-ask"
        @click="askAboutSelected"
      />
    </header>

    <q-inner-loading :showing="loading" />

    <p v-if="!loading && !deals.length" class="deals__empty" data-test="deals-empty">
      Nothing in the pipeline yet. Ask the Analyst to screen a sale and it will put the lots worth
      bidding on here.
    </p>

    <table v-else class="deals__table" data-test="deals-table">
      <thead v-if="!isMobile">
        <tr>
          <th class="deals__pick"><span class="sr-only">Select</span></th>
          <th>Address</th>
          <th>Stage</th>
          <th>Next action</th>
          <th class="deals__num">MAO</th>
          <th class="deals__num">Offer</th>
          <th>Sale</th>
          <th>LOI</th>
          <th>Last Analyst note</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="deal in deals" :key="deal.id" data-test="deals-row">
          <td class="deals__pick">
            <input
              type="checkbox"
              :checked="selected.has(deal.parcel_number)"
              :aria-label="`Select ${deal.address ?? deal.parcel_number}`"
              data-test="deals-select"
              @change="toggle(deal.parcel_number)"
            />
          </td>
          <td class="deals__address">
            <button type="button" class="deals__link" data-test="deals-open" @click="openLot(deal)">
              {{ deal.address ?? deal.parcel_number }}
            </button>
            <span class="deals__sub">{{ deal.parcel_number }}</span>
          </td>
          <td>
            <select
              class="deals__stage"
              :value="deal.stage"
              :aria-label="`Stage for ${deal.address ?? deal.parcel_number}`"
              data-test="deals-stage"
              @change="setStage(deal, ($event.target as HTMLSelectElement).value as DealStage)"
            >
              <option v-for="stage in STAGES" :key="stage.value" :value="stage.value">
                {{ stage.label }}
              </option>
            </select>
          </td>
          <td class="deals__next" data-label="Next action">
            <span v-if="deal.next_action">{{ deal.next_action }}</span>
            <span v-else class="deals__muted">—</span>
            <span v-if="deal.next_action_due" class="deals__sub">{{ deal.next_action_due }}</span>
          </td>
          <td class="deals__num" data-label="MAO" data-test="deals-mao">
            {{ money(deal.max_allowable_offer) }}
          </td>
          <td class="deals__num" data-label="Offer" data-test="deals-offer">
            {{ money(deal.target_price) }}
          </td>
          <td data-label="Sale" data-test="deals-sale">
            <span v-if="deal.sale_date">{{ deal.sale_date }}</span>
            <span v-else class="deals__muted">not listed</span>
          </td>
          <td data-label="LOI">
            <button
              type="button"
              class="deals__link"
              data-test="deals-offer-letter"
              @click="offerFor = deal"
            >
              Offer letter
            </button>
          </td>
          <td class="deals__note" data-label="Last Analyst note" data-test="deals-note">
            <template v-if="noteFor(deal)">
              <span>{{ noteFor(deal) }}</span>
              <!-- Dated, because it is what the Analyst said then, not a fresh read. -->
              <span v-if="deal.analyst_note_at" class="deals__sub">
                {{ deal.analyst_note_at.slice(0, 10) }}
              </span>
            </template>
            <span v-else class="deals__muted">added by hand</span>
          </td>
        </tr>
      </tbody>
    </table>

    <GenerateOfferDialog
      v-if="offerFor"
      :model-value="offerFor !== null"
      :parcel-number="offerFor.parcel_number"
      :max-allowable-offer="offerFor.max_allowable_offer ?? null"
      @update:model-value="
        (open) => {
          if (!open) offerFor = null
        }
      "
    />
  </div>
</template>

<style scoped>
.deals {
  padding: 12px 16px 32px;
}
.deals__head {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 10px;
}
.deals__title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}
.deals__empty {
  color: var(--ls-muted, #6b7280);
  max-width: 40rem;
  font-size: 13.5px;
}
.deals__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.deals__table th {
  text-align: left;
  font-weight: 500;
  color: var(--ls-muted, #6b7280);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 6px 10px 6px 0;
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
}
.deals__table td {
  padding: 8px 10px 8px 0;
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  vertical-align: top;
}
.deals__num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.deals__pick {
  width: 28px;
}
.deals__link {
  border: 0;
  background: none;
  padding: 0;
  font: inherit;
  color: var(--ls-link, #1565c0);
  cursor: pointer;
  text-align: left;
  min-height: 32px;
}
.deals__sub,
.deals__muted {
  display: block;
  font-size: 11px;
  color: var(--ls-muted, #6b7280);
}
.deals__muted {
  display: inline;
}
.deals__stage {
  font: inherit;
  font-size: 12.5px;
  padding: 5px 6px;
  min-height: 34px;
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  background: var(--ls-surface, #fff);
  color: inherit;
}
.deals__note {
  max-width: 30ch;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

/* One card per deal on a phone: a table that scrolls sideways is a table nobody reads. */
@media (max-width: 1023px) {
  .deals__table,
  .deals__table tbody,
  .deals__table tr,
  .deals__table td {
    display: block;
    width: 100%;
  }
  .deals__table tr {
    border: 1px solid var(--ls-line, #e0e0e0);
    border-radius: 6px;
    padding: 8px 10px;
    margin-bottom: 8px;
  }
  .deals__table td {
    border: 0;
    padding: 3px 0;
  }
  /* The header row is gone on a phone, so each value carries its own label. */
  .deals__table td[data-label]::before {
    content: attr(data-label);
    display: block;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ls-muted);
    margin-top: 4px;
  }
  .deals__num {
    text-align: left;
  }
  .deals__note {
    max-width: none;
  }
}
</style>
