<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { BuyBoxPayload, BuyBoxTargetUse } from '@/lib/types'

const TARGET_USES: { label: string; value: BuyBoxTargetUse }[] = [
  { label: 'Build', value: 'build' },
  { label: 'Hold', value: 'hold' },
  { label: 'Flip', value: 'flip' },
]

const ASSUMPTION_FIELDS: { key: string; label: string; suffix: string; step: number }[] = [
  { key: 'construction_cost_per_sqft', label: 'Construction cost', suffix: '$/sqft', step: 5 },
  { key: 'soft_cost_pct', label: 'Soft costs', suffix: 'fraction of hard cost', step: 0.01 },
  { key: 'selling_cost_pct', label: 'Selling costs', suffix: 'fraction of ARV', step: 0.01 },
  { key: 'target_margin', label: 'Target margin', suffix: 'fraction of ARV', step: 0.01 },
]

const form = ref<BuyBoxPayload | null>(null)
const loading = ref(true)
const saving = ref(false)
const seeding = ref(false)
const error = ref<string | null>(null)
const saved = ref(false)
const ownerName = ref('')
const seedNote = ref<string | null>(null)
const zoningInput = ref('')
const ownedInput = ref('')

function assumption(key: string): number | null {
  return form.value?.assumptions[key] ?? null
}

function setAssumption(key: string, value: number | null): void {
  if (form.value === null) return
  const next = { ...form.value.assumptions }
  if (value === null || Number.isNaN(value)) delete next[key]
  else next[key] = value
  form.value.assumptions = next
}

function splitList(raw: string): string[] {
  return raw
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
}

onMounted(async () => {
  try {
    const record = await api.getBuyBox()
    form.value = {
      areas: record.areas,
      max_bid: record.max_bid,
      target_use: record.target_use,
      min_lot_sqft: record.min_lot_sqft,
      zoning_codes: record.zoning_codes,
      exclude_city_neighbor: record.exclude_city_neighbor,
      exclude_open_violations: record.exclude_open_violations,
      exclude_historic: record.exclude_historic,
      exclude_flood: record.exclude_flood,
      assumptions: record.assumptions,
      owned_parcels: record.owned_parcels,
    }
    zoningInput.value = record.zoning_codes.join(', ')
    ownedInput.value = record.owned_parcels.join('\n')
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Your buy box could not be loaded.'
  } finally {
    loading.value = false
  }
})

async function save(): Promise<void> {
  if (form.value === null) return
  saving.value = true
  error.value = null
  saved.value = false
  try {
    const record = await api.saveBuyBox({
      ...form.value,
      zoning_codes: splitList(zoningInput.value),
      owned_parcels: splitList(ownedInput.value),
    })
    form.value.zoning_codes = record.zoning_codes
    form.value.owned_parcels = record.owned_parcels
    zoningInput.value = record.zoning_codes.join(', ')
    ownedInput.value = record.owned_parcels.join('\n')
    saved.value = true
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Your buy box could not be saved.'
  } finally {
    saving.value = false
  }
}

async function seedFromOwner(): Promise<void> {
  const name = ownerName.value.trim()
  if (name.length === 0 || form.value === null) return
  seeding.value = true
  error.value = null
  try {
    const result = await api.seedOwnedParcels(name)
    form.value.owned_parcels = result.owned_parcels
    ownedInput.value = result.owned_parcels.join('\n')
    seedNote.value =
      result.added.length === 0
        ? `No new parcels are recorded to ${result.owner_name} in ${result.source}.`
        : `Added ${result.added.length} parcel${result.added.length === 1 ? '' : 's'} owned by ${result.owner_name}, per ${result.source}.`
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Those parcels could not be seeded.'
  } finally {
    seeding.value = false
  }
}
</script>

<template>
  <div class="buy-box-editor" data-test="buy-box-editor">
    <div v-if="loading" class="text-body2 lot-text-muted">Loading your buy box…</div>

    <template v-else-if="form">
      <div class="text-subtitle2">Buy box</div>
      <p class="text-caption lot-text-muted q-mb-md">
        Every screen, and every Sale Packet, screens lots against these numbers.
      </p>

      <div class="row q-col-gutter-md">
        <q-input
          v-model.number="form.max_bid"
          class="col-12 col-sm-6"
          type="number"
          min="0"
          outlined
          dense
          label="Max bid"
          prefix="$"
          data-test="buy-box-max-bid"
        />
        <q-select
          v-model="form.target_use"
          class="col-12 col-sm-6"
          :options="TARGET_USES"
          emit-value
          map-options
          outlined
          dense
          label="Target use"
          data-test="buy-box-target-use"
        />
        <q-input
          v-model.number="form.min_lot_sqft"
          class="col-12 col-sm-6"
          type="number"
          min="0"
          outlined
          dense
          label="Minimum lot size"
          suffix="sqft"
          hint="640 sqft is a 16x40 rowhouse lot"
          data-test="buy-box-min-lot"
        />
        <q-input
          v-model="zoningInput"
          class="col-12 col-sm-6"
          outlined
          dense
          label="Zoning codes"
          hint="Comma separated. Empty means every district."
          data-test="buy-box-zoning"
        />
      </div>

      <div class="text-subtitle2 q-mt-lg">Rule out</div>
      <div class="row q-col-gutter-sm">
        <q-toggle
          v-model="form.exclude_historic"
          class="col-12 col-sm-6"
          label="Historic districts"
          data-test="buy-box-exclude-historic"
        />
        <q-toggle
          v-model="form.exclude_flood"
          class="col-12 col-sm-6"
          label="Flood zones"
          data-test="buy-box-exclude-flood"
        />
        <q-toggle
          v-model="form.exclude_open_violations"
          class="col-12 col-sm-6"
          label="Open L&I violations"
        />
        <q-toggle
          v-model="form.exclude_city_neighbor"
          class="col-12 col-sm-6"
          label="City-owned neighbours"
        />
      </div>

      <div class="text-subtitle2 q-mt-lg">Deal assumptions</div>
      <p class="text-caption lot-text-muted">
        Left blank, each falls back to the platform default. Filled in, it moves your MAO.
      </p>
      <div class="row q-col-gutter-md">
        <q-input
          v-for="field in ASSUMPTION_FIELDS"
          :key="field.key"
          class="col-12 col-sm-6"
          type="number"
          :model-value="assumption(field.key)"
          :step="field.step"
          min="0"
          outlined
          dense
          clearable
          :label="field.label"
          :suffix="field.suffix"
          :data-test="`buy-box-${field.key}`"
          @update:model-value="setAssumption(field.key, $event === null ? null : Number($event))"
        />
      </div>

      <div class="text-subtitle2 q-mt-lg">Parcels you already own</div>
      <div class="row q-col-gutter-md items-end">
        <q-input
          v-model="ownerName"
          class="col"
          outlined
          dense
          label="OPA owner name"
          hint="Seeds from the city's recorded owner, then edit by hand"
          data-test="buy-box-owner-name"
        />
        <div class="col-auto">
          <q-btn
            no-caps
            outline
            color="primary"
            label="Seed from OPA"
            :loading="seeding"
            :disable="ownerName.trim().length === 0"
            data-test="buy-box-seed"
            @click="seedFromOwner"
          />
        </div>
      </div>
      <div
        v-if="seedNote"
        class="text-caption lot-text-muted q-mt-xs"
        data-test="buy-box-seed-note"
      >
        {{ seedNote }}
      </div>
      <q-input
        v-model="ownedInput"
        class="q-mt-sm"
        type="textarea"
        autogrow
        outlined
        dense
        label="Owned parcels"
        hint="One parcel number per line"
        data-test="buy-box-owned"
      />

      <div class="row items-center q-gutter-sm q-mt-lg">
        <q-btn
          no-caps
          color="primary"
          label="Save buy box"
          :loading="saving"
          data-test="buy-box-save"
          @click="save"
        />
        <span v-if="saved" class="text-caption text-positive" data-test="buy-box-saved">Saved</span>
      </div>
    </template>

    <q-banner v-if="error" dense class="bg-red-1 q-mt-md" data-test="buy-box-error">
      {{ error }}
    </q-banner>
  </div>
</template>
