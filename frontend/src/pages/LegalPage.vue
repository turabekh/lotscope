<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '@/lib/api'
import type { PolicyDocument, PolicySummary } from '@/lib/types'

const route = useRoute()

const index = ref<PolicySummary[]>([])
const document = ref<PolicyDocument | null>(null)
const loading = ref(true)
const unpublished = ref(false)

const slug = computed(() => (typeof route.params.slug === 'string' ? route.params.slug : ''))
const title = computed(
  () => document.value?.title ?? index.value.find((p) => p.slug === slug.value)?.title ?? 'Policy',
)

const paragraphs = computed(() =>
  (document.value?.body_markdown ?? '')
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0),
)

async function load(): Promise<void> {
  loading.value = true
  unpublished.value = false
  document.value = null
  try {
    index.value = await api.getPolicyIndex()
  } catch {
    index.value = []
  }
  if (!slug.value) {
    loading.value = false
    return
  }
  try {
    document.value = await api.getPolicy(slug.value)
  } catch {
    unpublished.value = true
  } finally {
    loading.value = false
  }
}

watch(slug, load, { immediate: true })
</script>

<template>
  <q-page class="q-pa-md">
    <div class="legal-wrap">
      <nav class="index" data-test="policy-index">
        <router-link
          v-for="policy in index"
          :key="policy.slug"
          :to="{ name: 'legal', params: { slug: policy.slug } }"
          class="index-link"
          :class="{ current: policy.slug === slug }"
        >
          {{ policy.title }}
          <span v-if="!policy.published" class="index-pending">not published</span>
        </router-link>
      </nav>

      <article class="doc">
        <h1 class="doc-title">{{ title }}</h1>

        <div v-if="loading" class="note">Loading…</div>

        <div v-else-if="unpublished" class="note pending" data-test="policy-unpublished">
          <strong>This policy has not been published yet.</strong>
          Nothing is shown here in place of it, because a draft or sample would be mistaken for the
          real terms. If you need this document before it is published, contact us and we will send
          the current position in writing.
        </div>

        <template v-else-if="document">
          <div class="doc-meta" data-test="policy-meta">
            Version {{ document.version }} · effective
            {{ new Date(document.effective_date).toLocaleDateString() }}
          </div>
          <p v-for="(block, i) in paragraphs" :key="i" class="doc-body">{{ block }}</p>
        </template>

        <div v-else class="note">Choose a policy from the list.</div>
      </article>
    </div>
  </q-page>
</template>

<style scoped>
.legal-wrap {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 24px;
  max-width: 1000px;
  margin: 0 auto;
}
@media (max-width: 700px) {
  .legal-wrap {
    grid-template-columns: 1fr;
  }
}
.index {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.index-link {
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  text-decoration: none;
  color: var(--lot-ink);
  font-size: 13px;
}
.index-link:hover {
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
}
.index-link.current {
  background: var(--lot-accent-soft);
  color: var(--lot-accent-ink);
  font-weight: 600;
}
.index-pending {
  font-size: 11px;
  color: var(--lot-muted);
}
.doc-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 6px;
}
.doc-meta {
  font-size: 12px;
  color: var(--lot-muted);
  margin-bottom: 14px;
}
.doc-body {
  font-size: 14px;
  line-height: 1.6;
  color: var(--lot-ink);
  margin: 0 0 12px;
  white-space: pre-wrap;
}
.note {
  font-size: 13.5px;
  color: var(--lot-muted);
  line-height: 1.55;
}
.note.pending {
  padding: 12px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
}
</style>
