<script setup lang="ts">
// Step 3.1 gives the Analyst its route and nothing more. Step 3.2 builds the conversation:
// the thread, the streaming tool cards, the evidence drawer. Until then this says what it
// is rather than pretending to be finished.
import { onMounted, ref } from 'vue'

import { api, ApiError } from '@/lib/api'
import type { BriefRecord } from '@/lib/types'

const brief = ref<BriefRecord | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    brief.value = await api.todaysBrief()
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load today’s brief.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <q-page class="q-pa-lg">
    <h1 class="text-h6 q-mt-none q-mb-md">Analyst</h1>

    <q-banner class="bg-grey-2 q-mb-lg" dense>
      The conversation lands in the next step. Today's brief is below.
    </q-banner>

    <q-spinner v-if="loading" size="24px" />
    <q-banner v-else-if="error" class="bg-red-1 text-red-9" dense>{{ error }}</q-banner>

    <template v-else-if="brief">
      <div class="text-subtitle2 q-mb-xs">
        Brief for {{ brief.brief_date }} — {{ brief.signal_count }} change<span
          v-if="brief.signal_count !== 1"
          >s</span
        >
        overnight
      </div>
      <p class="brief-body">{{ brief.text }}</p>

      <div v-if="brief.signals.length" class="q-mt-md">
        <div class="text-caption text-grey-8 q-mb-xs">What it was built from</div>
        <q-list bordered separator dense>
          <q-item v-for="signal in brief.signals" :key="signal.headline">
            <q-item-section>
              <q-item-label>{{ signal.headline }}</q-item-label>
              <q-item-label caption>{{ signal.source }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </template>

    <p v-else class="text-grey-8">
      Nothing changed overnight on anything you are watching, so there is no brief today.
    </p>
  </q-page>
</template>

<style scoped>
.brief-body {
  white-space: pre-wrap;
  line-height: 1.6;
  max-width: 46rem;
}
</style>
