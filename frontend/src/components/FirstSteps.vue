<script setup lang="ts">
import { onMounted } from 'vue'

import { useFirstStepsStore } from '@/stores/firstSteps'
import { useMarketStore } from '@/stores/market'

const firstSteps = useFirstStepsStore()
const market = useMarketStore()

onMounted(() => {
  void firstSteps.refresh()
})
</script>

<template>
  <q-card
    v-if="firstSteps.resolved && !firstSteps.allDone"
    flat
    bordered
    class="rounded-borders"
    data-test="first-steps"
  >
    <q-card-section class="q-py-sm">
      <div class="head">
        <div class="section-title">
          <q-icon name="flag" size="18px" class="q-mr-xs" />Get set up
        </div>
        <span class="count" data-test="first-steps-count">
          {{ firstSteps.completed }} of {{ firstSteps.steps.length }}
        </span>
      </div>

      <q-linear-progress
        :value="firstSteps.completed / firstSteps.steps.length"
        rounded
        size="4px"
        class="q-mb-sm"
      />

      <router-link
        v-for="step in firstSteps.steps"
        :key="step.code"
        :to="{ name: step.routeName, params: { market: market.active } }"
        class="step"
        :class="{ done: step.done }"
        :data-test="`first-step-${step.code}`"
      >
        <q-icon
          :name="step.done ? 'check_circle' : 'radio_button_unchecked'"
          size="18px"
          class="step-icon"
        />
        <span class="step-text">
          <span class="step-label">{{ step.label }}</span>
          <span class="step-detail">{{ step.detail }}</span>
        </span>
      </router-link>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.count {
  font-size: 12px;
  color: var(--lot-muted);
}
.step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 7px 8px;
  border-radius: var(--lot-radius-sm);
  text-decoration: none;
  color: var(--lot-ink);
}
.step:hover {
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
}
.step-icon {
  color: var(--lot-faint);
  margin-top: 1px;
  flex: none;
}
.step.done .step-icon {
  color: var(--lot-positive, #21ba45);
}
.step.done .step-label {
  text-decoration: line-through;
  color: var(--lot-muted);
}
.step-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.step-label {
  font-size: 13px;
  font-weight: 600;
}
.step-detail {
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.35;
}
</style>
