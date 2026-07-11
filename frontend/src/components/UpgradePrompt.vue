<script setup lang="ts">
import { computed } from 'vue'

import type { UpgradeCap } from '@/lib/upgrade'
import { UPGRADE_COPY } from '@/lib/upgrade'

const props = withDefaults(
  defineProps<{
    cap: UpgradeCap
    variant?: 'card' | 'banner'
    dismissible?: boolean
    cta?: string
  }>(),
  { variant: 'card', dismissible: false, cta: 'See plans' },
)

const emit = defineEmits<{ dismiss: [] }>()

const copy = computed(() => UPGRADE_COPY[props.cap])
</script>

<template>
  <div class="upgrade-prompt" :class="variant">
    <q-icon name="workspace_premium" size="22px" class="up-icon" />
    <div class="up-body">
      <div class="up-headline">{{ copy.headline }}</div>
      <div class="up-detail">{{ copy.detail }}</div>
    </div>
    <div class="up-actions">
      <q-btn unelevated no-caps color="primary" :label="cta" :to="{ name: 'account' }" />
      <q-btn
        v-if="dismissible"
        flat
        dense
        round
        icon="close"
        aria-label="Dismiss"
        @click="emit('dismiss')"
      />
    </div>
  </div>
</template>

<style scoped>
.upgrade-prompt {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius);
  background: var(--lot-accent-soft, rgba(21, 101, 192, 0.08));
}
.up-icon {
  color: var(--q-primary);
  flex: 0 0 auto;
  margin-top: 2px;
}
.up-body {
  flex: 1 1 auto;
  min-width: 0;
}
.up-headline {
  font-weight: 600;
  line-height: 1.3;
}
.up-detail {
  font-size: 13px;
  color: var(--lot-faint, #616161);
  margin-top: 3px;
  line-height: 1.35;
}
.up-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}
.upgrade-prompt.card {
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 420px;
  margin: 0 auto;
}
.card .up-actions {
  margin-top: 6px;
}
@media (max-width: 640px) {
  .upgrade-prompt.banner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
