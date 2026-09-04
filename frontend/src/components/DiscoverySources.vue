<script setup lang="ts">
import { computed } from 'vue'

interface DiscoverySource {
  label: string
  icon: string
  name: string
  blurb: string
}

const sources = computed<DiscoverySource[]>(() => [
  {
    label: 'Feed',
    icon: 'bolt',
    name: 'feed',
    blurb: 'New and changed lots since your last visit',
  },
  {
    label: 'Sheriff sales',
    icon: 'gavel',
    name: 'sheriff-sales',
    blurb: 'Lots heading to forced sale',
  },
  {
    label: 'Top plays',
    icon: 'dashboard_customize',
    name: 'top-plays',
    blurb: 'Ranked assemblage opportunities',
  },
])

const visibleSources = computed<DiscoverySource[]>(() => sources.value.filter(() => true))
</script>

<template>
  <div v-if="visibleSources.length" class="sources" data-test="discovery-sources">
    <div class="sources-title">Other ways to find lots</div>
    <router-link
      v-for="source in visibleSources"
      :key="source.name"
      :to="{ name: source.name }"
      class="source"
    >
      <q-icon :name="source.icon" size="18px" class="source-icon" />
      <span class="source-text">
        <span class="source-label">{{ source.label }}</span>
        <span class="source-blurb">{{ source.blurb }}</span>
      </span>
      <q-icon name="chevron_right" size="16px" class="source-chevron" />
    </router-link>
  </div>
</template>

<style scoped>
.sources {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.08));
}
.sources-title {
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.source {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: var(--lot-radius-sm);
  text-decoration: none;
  color: var(--lot-ink);
}
.source:hover {
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
}
.source-icon {
  color: var(--lot-accent);
  flex: none;
}
.source-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.source-label {
  font-size: 13px;
  font-weight: 600;
}
.source-blurb {
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.3;
}
.source-chevron {
  color: var(--lot-faint);
  flex: none;
}
</style>
