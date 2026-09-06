<script setup lang="ts">
import { ref } from 'vue'

import { api } from '@/lib/api'
import type { ShowMeTarget } from '@/lib/sourceLinks'

const props = defineProps<{ target: ShowMeTarget }>()

const open = ref(false)
const loading = ref(false)
const provision = ref<{
  cite: string
  heading: string | null
  text: string
  source_url: string
} | null>(null)
const failed = ref<string | null>(null)

async function toggle(): Promise<void> {
  open.value = !open.value
  if (!open.value || props.target.kind !== 'provision' || provision.value) return
  loading.value = true
  failed.value = null
  try {
    provision.value = await api.getProvision(props.target.provisionId)
  } catch {
    failed.value = 'That provision is not in the corpus we hold.'
  } finally {
    loading.value = false
  }
}

function stamp(asOf: string | null): string {
  return asOf ? `as of ${asOf.slice(0, 10)}` : 'no as-of recorded'
}
</script>

<template>
  <span class="showme">
    <a
      v-if="target.kind === 'external'"
      :href="target.url"
      target="_blank"
      rel="noopener"
      class="showme__btn"
      data-test="show-me-external"
      >Show me</a
    >
    <button
      v-else
      type="button"
      class="showme__btn"
      :aria-expanded="open"
      data-test="show-me"
      @click="toggle"
    >
      Show me
    </button>

    <span v-if="open && target.kind === 'stored'" class="showme__pop" data-test="show-me-stored">
      <!-- No public URL exists for this one, so the honest answer is which of our sources
           said it and when that source was last read. -->
      No public page for this. It comes from <strong>{{ target.source }}</strong
      >, {{ stamp(target.asOf) }}.
    </span>

    <span
      v-if="open && target.kind === 'provision'"
      class="showme__pop"
      data-test="show-me-provision"
    >
      <span v-if="loading">Loading…</span>
      <span v-else-if="failed">{{ failed }}</span>
      <template v-else-if="provision">
        <strong>{{ provision.cite }}</strong>
        <span v-if="provision.heading"> — {{ provision.heading }}</span>
        <span class="showme__text">{{ provision.text }}</span>
        <a :href="provision.source_url" target="_blank" rel="noopener"
          >Read it on the Code Library</a
        >
      </template>
    </span>
  </span>
</template>

<style scoped>
.showme {
  position: relative;
  display: inline-block;
}
.showme__btn {
  border: 0;
  background: none;
  padding: 0 0 0 6px;
  font: inherit;
  font-size: 11.5px;
  color: var(--ls-link, #1565c0);
  text-decoration: underline;
  cursor: pointer;
  min-height: 24px;
}
.showme__pop {
  display: block;
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  background: var(--ls-surface, #fff);
  font-size: 12px;
  line-height: 1.5;
  max-width: 46rem;
}
.showme__text {
  display: block;
  white-space: pre-wrap;
  margin: 6px 0;
  max-height: 16rem;
  overflow-y: auto;
}
</style>
