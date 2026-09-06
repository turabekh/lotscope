<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import type { LotSection } from '@/lib/sourceLinks'

const props = defineProps<{ sections: { id: LotSection; label: string }[] }>()

const active = ref<LotSection | null>(props.sections[0]?.id ?? null)
let observer: IntersectionObserver | null = null

onMounted(() => {
  // Highlight whichever section the reader is actually looking at. The top margin keeps
  // the sticky nav itself from counting as the viewport edge. Where the API is missing
  // the nav still navigates; it just does not follow the scroll.
  if (typeof IntersectionObserver === 'undefined') return
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
      if (visible) active.value = visible.target.id as LotSection
    },
    { rootMargin: '-64px 0px -55% 0px', threshold: 0 },
  )
  for (const section of props.sections) {
    const node = document.getElementById(section.id)
    if (node) observer.observe(node)
  }
})

onBeforeUnmount(() => observer?.disconnect())

async function go(id: LotSection): Promise<void> {
  const node = document.getElementById(id)
  if (!node) return
  node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  // The evidence sections load on their own, so the page grows under a scroll that has
  // already been aimed. Re-aim it a few times while the layout settles, then stop —
  // beyond that the reader is the one scrolling.
  const settled = node.getBoundingClientRect().top
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 250))
    const drift = Math.abs(node.getBoundingClientRect().top - settled)
    if (drift > 24) node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
</script>

<template>
  <nav class="lotnav" aria-label="Sections" data-test="lot-section-nav">
    <button
      v-for="section in sections"
      :key="section.id"
      type="button"
      class="lotnav__item"
      :class="{ 'lotnav__item--on': active === section.id }"
      :aria-current="active === section.id ? 'true' : undefined"
      :data-test="`lot-nav-${section.id}`"
      @click="void go(section.id)"
    >
      {{ section.label }}
    </button>
  </nav>
</template>

<style scoped>
.lotnav {
  position: sticky;
  top: 0;
  z-index: 5;
  /* The scroll pane is a flex column, and a child with overflow of its own takes an
     automatic minimum height of zero — without this the nav is squashed to a 13px band
     and the page scrolls through it. */
  flex: 0 0 auto;
  display: flex;
  gap: 2px;
  overflow-x: auto;
  padding: 8px 4px 6px;
  background: var(--ls-surface, #fff);
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  scrollbar-width: none;
}
.lotnav::-webkit-scrollbar {
  display: none;
}
.lotnav__item {
  flex: 0 0 auto;
  border: 0;
  border-radius: 4px;
  background: none;
  color: var(--ls-muted, #6b7280);
  font: inherit;
  font-size: 12px;
  padding: 6px 10px;
  min-height: 34px;
  cursor: pointer;
  white-space: nowrap;
}
.lotnav__item--on {
  background: var(--ls-selected, #eef2f7);
  color: inherit;
}
</style>
