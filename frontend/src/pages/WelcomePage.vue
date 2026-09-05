<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="welcome">
    <div class="welcome__inner">
      <h1 class="welcome__brand">LotScope</h1>
      <p class="welcome__pitch">
        An AI acquisitions analyst that works Philadelphia vacant land for you. It screens a
        sheriff-sale list against your buy box, reads the city's records live when you ask a
        question that turns on them, and tells you what it could not verify.
      </p>
      <q-btn
        unelevated
        color="primary"
        label="Sign in"
        no-caps
        @click="router.push({ name: 'login' })"
      />
      <q-btn flat no-caps label="Create an account" @click="router.push({ name: 'register' })" />
    </div>
  </div>
</template>

<style scoped>
.welcome {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
}

.welcome__inner {
  max-width: 30rem;
}

.welcome__brand {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 12px;
}

.welcome__pitch {
  margin: 0 0 24px;
  line-height: 1.6;
}
</style>
