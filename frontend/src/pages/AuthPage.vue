<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ mode: 'login' | 'register' }>()

const store = useAuthStore()
const { loading, error } = storeToRefs(store)
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const fullName = ref('')

async function submit(): Promise<void> {
  try {
    if (props.mode === 'login') {
      await store.login(email.value.trim(), password.value)
    } else {
      await store.register({
        email: email.value.trim(),
        password: password.value,
        full_name: fullName.value.trim() || null,
      })
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app'
    await router.push(redirect)
  } catch {
    // error surfaced via store.error
  }
}
</script>

<template>
  <div class="auth-page">
    <q-card flat bordered class="auth-card">
      <q-card-section class="text-center q-pb-none">
        <q-icon name="location_city" color="primary" size="40px" />
        <div class="text-h5 q-mt-xs">LotScope <span class="text-weight-light">PHL</span></div>
        <div class="text-subtitle2 text-grey-7">
          {{ mode === 'login' ? 'Sign in to your account' : 'Create your free account' }}
        </div>
      </q-card-section>

      <q-card-section class="q-gutter-sm">
        <q-input v-if="mode === 'register'" v-model="fullName" outlined label="Name (optional)" />
        <q-input
          v-model="email"
          autofocus
          outlined
          type="email"
          label="Email"
          @keyup.enter="submit"
        />
        <q-input
          v-model="password"
          outlined
          type="password"
          label="Password"
          :hint="mode === 'register' ? 'At least 8 characters' : ''"
          @keyup.enter="submit"
        />
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>
        <q-btn
          class="full-width q-mt-sm"
          unelevated
          color="primary"
          :label="mode === 'login' ? 'Sign in' : 'Create account'"
          :loading="loading"
          @click="submit"
        />
      </q-card-section>

      <q-separator />
      <q-card-section class="text-center">
        <template v-if="mode === 'login'">
          <span class="text-grey-7">New to LotScope? </span>
          <q-btn
            flat
            dense
            no-caps
            color="primary"
            label="Create an account"
            :to="{ name: 'register', query: route.query }"
          />
        </template>
        <template v-else>
          <span class="text-grey-7">Already have an account? </span>
          <q-btn
            flat
            dense
            no-caps
            color="primary"
            label="Sign in"
            :to="{ name: 'login', query: route.query }"
          />
        </template>
      </q-card-section>
      <q-card-section class="text-center q-pt-none">
        <q-btn flat dense no-caps color="grey-7" icon="arrow_back" label="Back to map" to="/" />
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eceff1;
  padding: 16px;
}
.auth-card {
  width: 400px;
  max-width: 94vw;
  border-radius: 14px;
}
</style>
