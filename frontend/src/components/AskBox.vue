<script setup lang="ts">
import { ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { ParcelAnswer } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const question = ref('')
const answer = ref<ParcelAnswer | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function ask(): Promise<void> {
  const text = question.value.trim()
  if (text === '') return
  loading.value = true
  error.value = null
  try {
    answer.value = await api.ask(props.parcelNumber, text)
  } catch (cause) {
    answer.value = null
    error.value = cause instanceof ApiError ? cause.message : 'Failed to get an answer.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <q-card flat bordered>
    <q-card-section>
      <div class="text-subtitle1 q-mb-sm">Ask the parcel</div>
      <q-input
        v-model="question"
        dense
        outlined
        placeholder="Can I build a duplex here?"
        @keyup.enter="ask"
      >
        <template #after>
          <q-btn round dense icon="send" :loading="loading" @click="ask" />
        </template>
      </q-input>
      <q-banner v-if="error" dense class="bg-red-1 text-negative q-mt-sm">{{ error }}</q-banner>
      <div v-if="answer" class="q-mt-md">
        <div class="text-body2">{{ answer.answer }}</div>
        <div class="text-caption text-grey q-mt-sm">
          Confidence: {{ answer.confidence }} · Informational only
        </div>
        <div class="q-gutter-xs q-mt-xs">
          <q-chip
            v-for="(citation, index) in answer.citations"
            :key="index"
            dense
            outline
            :label="`${citation.source} ${citation.section}`"
          />
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>
