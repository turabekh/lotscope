<script setup lang="ts">
import { computed, ref } from 'vue'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()

const sending = ref(false)
const sent = ref(false)
const address = computed(() => store.user?.email ?? store.pendingVerificationEmail)

async function resend(): Promise<void> {
  if (address.value === null || address.value === undefined) return
  sending.value = true
  try {
    await store.resendVerification(address.value)
    sent.value = true
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <q-banner v-if="store.emailUnverified" dense class="verify-banner" data-test="verify-banner">
    <template #avatar>
      <q-icon name="mark_email_unread" color="warning" />
    </template>
    Verify your email to keep using LotScope. We sent a link to
    {{ address ?? 'the address you signed up with' }}.
    <template #action>
      <q-btn
        flat
        dense
        no-caps
        color="primary"
        :loading="sending"
        :disable="sent"
        :label="sent ? 'Sent' : 'Resend the link'"
        data-test="verify-banner-resend"
        @click="resend"
      />
    </template>
  </q-banner>
</template>

<style scoped>
.verify-banner {
  background: #fff8e1;
  border-bottom: 1px solid #ffe082;
}
</style>
