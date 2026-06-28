<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const { dialogOpen, loading, error } = storeToRefs(store)

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const fullName = ref('')

function toggleMode(): void {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  store.error = null
}

async function submit(): Promise<void> {
  try {
    if (mode.value === 'login') {
      await store.login(email.value.trim(), password.value)
    } else {
      await store.register({
        email: email.value.trim(),
        password: password.value,
        full_name: fullName.value.trim() || null,
      })
    }
    password.value = ''
  } catch {
    // error surfaced via store.error
  }
}
</script>

<template>
  <q-dialog v-model="dialogOpen">
    <q-card class="auth-card">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="location_city" color="primary" size="24px" class="q-mr-sm" />
        <div class="text-h6">{{ mode === 'login' ? 'Sign in' : 'Create account' }}</div>
        <q-space />
        <q-btn v-close-popup flat round dense icon="close" />
      </q-card-section>

      <q-card-section class="q-gutter-sm">
        <div class="text-body2 text-grey-7">
          {{
            mode === 'login'
              ? 'Sign in to ask the AI about any parcel.'
              : 'Create a free account to use Ask the Parcel.'
          }}
        </div>
        <q-input
          v-if="mode === 'register'"
          v-model="fullName"
          outlined
          dense
          label="Name (optional)"
        />
        <q-input
          v-model="email"
          autofocus
          outlined
          dense
          type="email"
          label="Email"
          @keyup.enter="submit"
        />
        <q-input
          v-model="password"
          outlined
          dense
          type="password"
          label="Password"
          :hint="mode === 'register' ? 'At least 8 characters' : ''"
          @keyup.enter="submit"
        />
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>
      </q-card-section>

      <q-card-actions align="between" class="q-px-md q-pb-md">
        <q-btn
          flat
          dense
          no-caps
          color="primary"
          :label="mode === 'login' ? 'Need an account?' : 'Have an account?'"
          @click="toggleMode"
        />
        <q-btn
          unelevated
          color="primary"
          :label="mode === 'login' ? 'Sign in' : 'Sign up'"
          :loading="loading"
          @click="submit"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.auth-card {
  min-width: 340px;
  max-width: 92vw;
  border-radius: 12px;
}
</style>
