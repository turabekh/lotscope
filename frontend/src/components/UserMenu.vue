<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const { user, isAuthenticated } = storeToRefs(store)

const initial = computed(() => (user.value?.email ?? '?').charAt(0).toUpperCase())
</script>

<template>
  <q-btn
    v-if="!isAuthenticated"
    flat
    dense
    no-caps
    icon="login"
    label="Sign in"
    @click="store.openDialog()"
  />
  <q-btn v-else flat dense round aria-label="Account">
    <q-avatar size="30px" color="white" text-color="primary" class="text-weight-bold">
      {{ initial }}
    </q-avatar>
    <q-menu anchor="bottom right" self="top right">
      <q-list style="min-width: 200px">
        <q-item>
          <q-item-section>
            <q-item-label class="ellipsis">{{ user?.full_name ?? user?.email }}</q-item-label>
            <q-item-label caption>{{ user?.email }} · {{ user?.tier }} tier</q-item-label>
          </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-close-popup clickable @click="store.logout()">
          <q-item-section avatar><q-icon name="logout" /></q-item-section>
          <q-item-section>Sign out</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>
