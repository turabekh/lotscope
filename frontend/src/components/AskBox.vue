<script setup lang="ts">
import { ref, watch } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { ParcelAnswer } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const question = ref('')
const answer = ref<ParcelAnswer | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const suggestions = [
  'What can I build by right?',
  'How many units can I build by right?',
  'What is the height limit?',
  'What is the minimum lot size for this district?',
  'What are the setback requirements?',
  'Can I build multi-family housing here?',
  'Does this lot need a variance or special exception?',
  'What uses does this zoning district allow?',
]

watch(
  () => props.parcelNumber,
  () => {
    question.value = ''
    answer.value = null
    error.value = null
  },
)

async function ask(): Promise<void> {
  const text = question.value.trim()
  if (text === '') return
  loading.value = true
  error.value = null
  try {
    answer.value = await api.ask(props.parcelNumber, text)
    question.value = ''
  } catch (cause) {
    answer.value = null
    error.value = cause instanceof ApiError ? cause.message : 'Failed to get an answer.'
  } finally {
    loading.value = false
  }
}

function askSuggestion(text: string): void {
  question.value = text
  void ask()
}
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section class="q-pb-sm">
      <div class="row items-center q-mb-sm">
        <q-icon name="forum" size="20px" class="q-mr-sm text-primary" />
        <div class="text-subtitle1">Ask the parcel</div>
      </div>
      <q-input
        v-model="question"
        dense
        outlined
        autogrow
        placeholder="Ask about zoning, height, units, uses…"
        :disable="loading"
        @keyup.enter="ask"
      >
        <template #append>
          <q-btn round dense flat icon="send" color="primary" :loading="loading" @click="ask" />
        </template>
      </q-input>

      <div class="q-gutter-xs q-mt-sm">
        <q-chip
          v-for="text in suggestions"
          :key="text"
          clickable
          dense
          outline
          color="primary"
          :disable="loading"
          @click="askSuggestion(text)"
        >
          {{ text }}
        </q-chip>
      </div>

      <q-banner v-if="error" dense class="bg-red-1 text-negative q-mt-sm rounded-borders">
        {{ error }}
      </q-banner>

      <q-slide-transition>
        <div v-if="answer" class="answer-block q-mt-md">
          <div class="text-body2 answer-text">{{ answer.answer }}</div>
          <div class="row items-center q-mt-sm">
            <q-chip
              dense
              square
              :color="answer.confidence === 'high' ? 'positive' : 'grey-6'"
              text-color="white"
            >
              {{ answer.confidence }} confidence
            </q-chip>
            <span class="text-caption text-grey-6 q-ml-sm">Informational only</span>
          </div>
          <div v-if="answer.citations.length" class="q-mt-sm">
            <div class="text-caption text-grey-7 q-mb-xs">Sources</div>
            <div class="q-gutter-xs">
              <q-chip
                v-for="(citation, index) in answer.citations"
                :key="index"
                dense
                outline
                color="grey-8"
                icon="description"
              >
                {{ citation.source }} · {{ citation.section }}
              </q-chip>
            </div>
          </div>
        </div>
      </q-slide-transition>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.answer-block {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}
.answer-text {
  white-space: pre-wrap;
  line-height: 1.5;
}
</style>
