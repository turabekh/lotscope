<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, ref, watch } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { CorrectionSection } from '@/lib/types'

const props = defineProps<{ modelValue: boolean; parcelNumber: string | undefined }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const $q = useQuasar()

const SECTIONS: { value: CorrectionSection; label: string }[] = [
  { value: 'buildability', label: 'What can be built' },
  { value: 'valuation', label: 'Value or comparables' },
  { value: 'deal', label: 'Deal economics' },
  { value: 'risk', label: 'Risks and records' },
  { value: 'ownership', label: 'Owner details' },
  { value: 'verdict', label: 'The overall verdict' },
  { value: 'other', label: 'Something else' },
]

const MIN_DESCRIPTION = 10

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const section = ref<CorrectionSection>('buildability')
const description = ref('')
const submitting = ref(false)

const tooShort = computed(() => description.value.trim().length < MIN_DESCRIPTION)

watch(open, (isOpen) => {
  if (isOpen) {
    section.value = 'buildability'
    description.value = ''
  }
})

async function submit(): Promise<void> {
  if (!props.parcelNumber || tooShort.value || submitting.value) return
  submitting.value = true
  try {
    await api.reportCorrection(props.parcelNumber, {
      section: section.value,
      description: description.value.trim(),
    })
    $q.notify({
      message: 'Thanks — we have logged this against the exact result you saw.',
      color: 'positive',
      icon: 'flag',
    })
    open.value = false
  } catch (cause) {
    const message = cause instanceof ApiError ? cause.message : 'Could not send the report.'
    $q.notify({ message, color: 'negative', icon: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <q-dialog v-model="open">
    <q-card class="correction-card">
      <div class="text-subtitle1 q-mb-xs">Report incorrect data</div>
      <div class="text-body2 lot-text-muted q-mb-md">
        We record the verdict version, the field state, and the source age exactly as they were when
        you opened this parcel, so the report stays meaningful after the next recompute.
      </div>

      <q-select
        v-model="section"
        :options="SECTIONS"
        option-value="value"
        option-label="label"
        emit-value
        map-options
        dense
        outlined
        label="What looks wrong?"
        class="q-mb-sm"
      />

      <q-input
        v-model="description"
        type="textarea"
        autogrow
        dense
        outlined
        label="What did you expect instead?"
        hint="Include what you checked against — a zoning map, a permit, a recorded deed."
        :rules="[() => !tooShort || 'Please describe the problem in a little more detail.']"
      />

      <div class="correction-actions">
        <q-btn flat no-caps label="Cancel" @click="open = false" />
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Send report"
          :disable="tooShort"
          :loading="submitting"
          data-test="submit-correction"
          @click="submit"
        />
      </div>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.correction-card {
  padding: 18px;
  width: 460px;
  max-width: 92vw;
  border-radius: var(--lot-radius);
}
.correction-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
</style>
