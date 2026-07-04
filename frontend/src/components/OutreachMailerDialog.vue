<script setup lang="ts">
import { computed, ref } from 'vue'

export interface MailerFields {
  fromName: string
  fromContact: string
  message: string
  onePerOwner: boolean
}

const props = defineProps<{
  modelValue: boolean
  subtitle: string
  submitting: boolean
  errorMessage: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [fields: MailerFields]
}>()

const fromName = ref('')
const fromContact = ref('')
const message = ref('')
const onePerOwner = ref(true)

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const canGenerate = computed(
  () => fromName.value.trim().length > 0 && fromContact.value.trim().length > 0,
)

function submit(): void {
  emit('submit', {
    fromName: fromName.value.trim(),
    fromContact: fromContact.value.trim(),
    message: message.value.trim(),
    onePerOwner: onePerOwner.value,
  })
}
</script>

<template>
  <q-dialog v-model="open">
    <q-card style="min-width: 380px; max-width: 460px">
      <q-card-section class="q-pb-none">
        <div class="text-h6">Direct-mail letters</div>
        <div class="text-body2 text-grey-7">{{ subtitle }}</div>
      </q-card-section>
      <q-card-section class="column q-gutter-sm">
        <q-input v-model="fromName" outlined dense label="Your name *" maxlength="120" autofocus />
        <q-input
          v-model="fromContact"
          outlined
          dense
          type="textarea"
          autogrow
          label="Return address / contact *"
          hint="Shown as the sender and signature block"
          maxlength="400"
        />
        <q-input
          v-model="message"
          outlined
          dense
          type="textarea"
          autogrow
          label="Custom message (optional)"
          hint="Leave blank for the default. Use {owner}, {property_address}, {parcel_number}."
          maxlength="4000"
        />
        <q-toggle
          v-model="onePerOwner"
          dense
          color="deep-purple-6"
          label="One letter per owner (skip duplicate owners)"
        />
        <q-banner v-if="errorMessage" dense class="bg-red-1 text-negative rounded-borders">
          {{ errorMessage }}
        </q-banner>
        <div class="text-caption text-grey-6">
          You are the sender and are responsible for compliance with direct-mail and Fair Housing
          rules. Informational only.
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn flat no-caps label="Cancel" color="grey-7" @click="open = false" />
        <q-btn
          unelevated
          no-caps
          color="deep-purple-6"
          icon="download"
          label="Generate PDF"
          :loading="submitting"
          :disable="!canGenerate"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
