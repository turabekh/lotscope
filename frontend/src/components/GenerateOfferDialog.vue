<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, ref, watch } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { OfferRequest } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  modelValue: boolean
  parcelNumber: string
  maxAllowableOffer: number | null
}>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const $q = useQuasar()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const offerPrice = ref<number | null>(null)
const allCash = ref(true)
const asIs = ref(true)
const earnestMoney = ref(1000)
const closeDays = ref(30)
const inspectionDays = ref(10)
const expiration = ref<string | null>(null)
const entityName = ref('')
const signerName = ref('')
const signerPhone = ref('')
const signerEmail = ref('')

const submitting = ref(false)

const noEconomics = computed(() => props.maxAllowableOffer === null)
const missingPrice = computed(() => noEconomics.value && (offerPrice.value ?? 0) <= 0)

function reset(): void {
  offerPrice.value = props.maxAllowableOffer
  allCash.value = true
  asIs.value = true
  earnestMoney.value = 1000
  closeDays.value = 30
  inspectionDays.value = 10
  expiration.value = null
  entityName.value = user.value?.entity_name ?? ''
  signerName.value = user.value?.signer_name ?? user.value?.full_name ?? ''
  signerPhone.value = user.value?.signer_phone ?? ''
  signerEmail.value = user.value?.signer_email ?? user.value?.email ?? ''
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) reset()
  },
  { immediate: true },
)

function close(): void {
  emit('update:modelValue', false)
}

async function submit(): Promise<void> {
  const payload: OfferRequest = {
    offer_price: offerPrice.value,
    all_cash: allCash.value,
    as_is: asIs.value,
    earnest_money: earnestMoney.value,
    close_days: closeDays.value,
    inspection_days: inspectionDays.value,
    expiration: expiration.value,
    entity_name: entityName.value || null,
    signer_name: signerName.value || null,
    signer_phone: signerPhone.value || null,
    signer_email: signerEmail.value || null,
  }
  submitting.value = true
  try {
    await api.generateOffer(props.parcelNumber, payload)
    $q.notify({ type: 'positive', message: 'Letter of intent downloaded.' })
    close()
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 409) {
      $q.notify({
        type: 'warning',
        message: 'No verdict economics for this parcel — enter a manual offer price to continue.',
      })
    } else {
      $q.notify({
        type: 'negative',
        message: cause instanceof ApiError ? cause.message : 'Could not generate the offer.',
      })
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <q-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
    <q-card style="min-width: 380px; max-width: 460px">
      <q-card-section class="row items-center">
        <div class="text-h6">Generate offer</div>
        <q-space />
        <q-btn v-close-popup flat round dense icon="close" />
      </q-card-section>

      <q-card-section class="q-gutter-sm">
        <q-banner v-if="noEconomics" dense class="bg-amber-1 text-amber-9 rounded-borders">
          This parcel has no computed verdict. Compute the verdict first, or enter a manual offer
          price below to generate the letter without the comp appendix framing.
        </q-banner>

        <q-input
          v-model.number="offerPrice"
          outlined
          dense
          type="number"
          label="Offer price"
          prefix="$"
          :hint="
            maxAllowableOffer !== null ? 'Defaults to the Maximum Allowable Offer' : 'Manual price'
          "
        />
        <div class="row q-col-gutter-sm">
          <q-toggle v-model="allCash" label="All cash" class="col" />
          <q-toggle v-model="asIs" label="As-is" class="col" />
        </div>
        <div class="row q-col-gutter-sm">
          <q-input
            v-model.number="earnestMoney"
            outlined
            dense
            type="number"
            label="EMD"
            prefix="$"
            class="col"
          />
          <q-input
            v-model.number="closeDays"
            outlined
            dense
            type="number"
            label="Close (days)"
            class="col"
          />
          <q-input
            v-model.number="inspectionDays"
            outlined
            dense
            type="number"
            label="Inspect (days)"
            class="col"
          />
        </div>
        <q-input
          v-model="expiration"
          outlined
          dense
          type="date"
          label="Offer valid through"
          stack-label
        />

        <div class="text-subtitle2 q-mt-sm">Signer</div>
        <q-input v-model="entityName" outlined dense label="Entity" />
        <q-input v-model="signerName" outlined dense label="Signer name" />
        <div class="row q-col-gutter-sm">
          <q-input v-model="signerPhone" outlined dense label="Phone" class="col" />
          <q-input v-model="signerEmail" outlined dense label="Email" class="col" />
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat no-caps label="Cancel" @click="close" />
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Download LOI"
          icon="picture_as_pdf"
          :loading="submitting"
          :disable="missingPrice"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
