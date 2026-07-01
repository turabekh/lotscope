<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import SavedLotsList from '@/components/SavedLotsList.vue'
import SavedSearchesList from '@/components/SavedSearchesList.vue'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const route = useRoute()
const router = useRouter()
const { alerts } = storeToRefs(useWatchlistStore())
const { newTotal } = storeToRefs(useSavedSearchesStore())

const tab = computed<string>({
  get: () => (route.query.tab === 'searches' ? 'searches' : 'lots'),
  set: (value) => {
    void router.replace({ query: { ...route.query, tab: value } })
  },
})
</script>

<template>
  <div class="lists-page">
    <div class="lists-wrap">
      <q-tabs
        v-model="tab"
        dense
        no-caps
        align="left"
        active-color="primary"
        indicator-color="primary"
        class="lists-tabs"
      >
        <q-tab name="lots">
          <div class="tab-inner">
            <q-icon name="bookmark" size="18px" class="q-mr-xs" />Saved lots
            <q-badge v-if="alerts > 0" color="negative" rounded class="q-ml-xs">{{
              alerts
            }}</q-badge>
          </div>
        </q-tab>
        <q-tab name="searches">
          <div class="tab-inner">
            <q-icon name="saved_search" size="18px" class="q-mr-xs" />Saved searches
            <q-badge v-if="newTotal > 0" color="negative" rounded class="q-ml-xs">
              {{ newTotal }}
            </q-badge>
          </div>
        </q-tab>
      </q-tabs>
      <q-separator />

      <q-tab-panels v-model="tab" animated keep-alive class="lists-panels">
        <q-tab-panel name="lots" class="lists-panel"><SavedLotsList /></q-tab-panel>
        <q-tab-panel name="searches" class="lists-panel"><SavedSearchesList /></q-tab-panel>
      </q-tab-panels>
    </div>
  </div>
</template>

<style scoped>
.lists-page {
  padding: 12px 16px;
}
.lists-wrap {
  max-width: 820px;
  margin: 0 auto;
}
.lists-tabs {
  color: var(--lot-muted);
}
.tab-inner {
  display: flex;
  align-items: center;
}
.lists-panels {
  background: transparent;
}
.lists-panel {
  padding: 16px 0;
}
</style>
