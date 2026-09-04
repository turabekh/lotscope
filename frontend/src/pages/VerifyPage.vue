<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const route = useRoute()
const router = useRouter()

const state = ref<'working' | 'failed'>('working')
const message = ref('')

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  if (!token) {
    state.value = 'failed'
    message.value = 'This link is missing its token.'
    return
  }
  try {
    await store.verifyEmail(token)
    await router.push({ name: 'home' })
  } catch {
    state.value = 'failed'
    message.value = store.error ?? 'This link is invalid or has expired.'
  }
})
</script>

<template>
  <div class="verify-page">
    <q-card flat bordered class="verify-card">
      <q-card-section class="text-center">
        <template v-if="state === 'working'">
          <q-spinner color="primary" size="32px" />
          <div class="text-body2 q-mt-sm" data-test="verify-working">Confirming your email…</div>
        </template>
        <template v-else>
          <q-icon name="link_off" color="negative" size="36px" />
          <div class="text-h6 q-mt-sm">Link not valid</div>
          <p class="text-body2 q-mt-sm" data-test="verify-failed">{{ message }}</p>
          <q-btn flat no-caps color="primary" label="Back to sign in" :to="{ name: 'login' }" />
        </template>
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped>
.verify-page {
  display: flex;
  justify-content: center;
  padding: 48px 16px;
}
.verify-card {
  width: 100%;
  max-width: 420px;
}
</style>
