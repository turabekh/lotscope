<script setup lang="ts">
import { storeToRefs } from 'pinia'

import PricingPlans from '@/components/PricingPlans.vue'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

const auth = useAuthStore()
const { isAuthenticated } = storeToRefs(auth)
const market = useMarketStore()

const features = [
  {
    icon: 'architecture',
    title: 'Buildability by-right',
    text: 'Zoning resolved against the full Title 14 standards — by-right units, height, and setbacks, or a clear "needs a variance".',
  },
  {
    icon: 'payments',
    title: 'Recorded-sale valuation',
    text: 'Land value from real nearby deeds, segmented by use class and trimmed of outliers, with a confidence signal.',
  },
  {
    icon: 'warning_amber',
    title: 'Risk flags',
    text: 'Tax delinquency, L&I violations, flood zones, and city ownership surfaced on every parcel.',
  },
  {
    icon: 'forum',
    title: 'Ask the parcel',
    text: 'Grounded, cited answers about what you can build — straight from Philadelphia’s zoning code.',
  },
]
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header class="bg-transparent text-white">
      <q-toolbar class="q-py-sm">
        <q-icon name="location_city" size="28px" class="q-mr-sm" />
        <q-toolbar-title class="text-weight-bold">
          LotScope <span class="text-weight-light">PHL</span>
        </q-toolbar-title>
        <template v-if="isAuthenticated">
          <q-btn
            unelevated
            color="white"
            text-color="primary"
            no-caps
            label="Open the map"
            :to="{ name: 'explore', params: { market: market.active } }"
          />
        </template>
        <template v-else>
          <q-btn flat no-caps label="Sign in" :to="{ name: 'login' }" />
          <q-btn unelevated color="white" text-color="primary" no-caps label="Get started" :to="{ name: 'register' }" />
        </template>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page>
        <section class="hero text-white">
          <div class="hero-inner">
            <div class="text-overline text-amber-4">Philadelphia parcel intelligence</div>
            <h1 class="hero-title">Know what can be built on any Philadelphia lot.</h1>
            <p class="hero-sub">
              Buildability, value, and risk for every parcel in the city — with the reasoning shown
              and the sources cited. One screen, one verdict.
            </p>
            <div class="q-gutter-sm q-mt-md">
              <q-btn
                v-if="isAuthenticated"
                unelevated
                size="lg"
                color="amber-7"
                text-color="dark"
                no-caps
                icon="map"
                label="Open the map"
                :to="{ name: 'explore', params: { market: market.active } }"
              />
              <template v-else>
                <q-btn
                  unelevated
                  size="lg"
                  color="amber-7"
                  text-color="dark"
                  no-caps
                  label="Create a free account"
                  :to="{ name: 'register' }"
                />
                <q-btn
                  outline
                  size="lg"
                  color="white"
                  no-caps
                  label="Sign in"
                  :to="{ name: 'login' }"
                />
              </template>
            </div>
            <div class="text-caption text-blue-2 q-mt-sm">
              Free plan includes 4 parcels and 10 AI questions a day.
            </div>
          </div>
        </section>

        <section class="features">
          <div class="features-grid">
            <q-card v-for="f in features" :key="f.title" flat bordered class="feature-card">
              <q-card-section>
                <q-icon :name="f.icon" size="32px" color="primary" />
                <div class="text-h6 q-mt-sm">{{ f.title }}</div>
                <div class="text-body2 text-grey-8 q-mt-xs">{{ f.text }}</div>
              </q-card-section>
            </q-card>
          </div>
        </section>

        <section class="pricing-section">
          <div class="pricing-inner">
            <div class="text-center q-mb-md">
              <div class="text-overline text-primary">Pricing</div>
              <div class="text-h4 text-weight-bold">Simple plans for every operator</div>
              <div class="text-body1 text-grey-7">
                Start free. Upgrade when you need unlimited research.
              </div>
            </div>
            <PricingPlans />
          </div>
        </section>

        <section class="cta">
          <div class="text-h5 text-weight-bold">Start exploring Philadelphia lots</div>
          <q-btn
            class="q-mt-md"
            unelevated
            size="lg"
            color="primary"
            no-caps
            :label="isAuthenticated ? 'Open the map' : 'Get started — it’s free'"
            :to="
              isAuthenticated
                ? { name: 'explore', params: { market: market.active } }
                : { name: 'register' }
            "
          />
          <div class="text-caption text-grey-6 q-mt-md">
            Informational only — not legal, financial, or real-estate advice. City data is provided
            as-is.
          </div>
        </section>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.hero {
  background:
    radial-gradient(120% 120% at 10% 0%, #6366f1 0%, transparent 55%),
    linear-gradient(135deg, #3730a3, #6d28d9);
  padding: 76px 24px 92px;
}
.hero-inner {
  max-width: 820px;
  margin: 0 auto;
}
.hero-title {
  font-size: clamp(28px, 5vw, 52px);
  line-height: 1.1;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 8px 0 12px;
}
.hero-sub {
  font-size: clamp(15px, 2.4vw, 20px);
  color: rgba(255, 255, 255, 0.86);
  max-width: 640px;
  margin: 0;
}
.features {
  padding: 56px 24px;
  background: var(--lot-bg);
}
.features-grid {
  max-width: 1040px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 16px;
}
.feature-card {
  border-radius: var(--lot-radius);
  height: 100%;
  background: var(--lot-surface);
  border-color: var(--lot-border);
  transition:
    transform 0.16s ease,
    box-shadow 0.16s ease;
}
.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--lot-shadow-lg);
}
.pricing-section {
  padding: 64px 24px;
  background: var(--lot-surface);
}
.pricing-inner {
  max-width: 1040px;
  margin: 0 auto;
}
.cta {
  text-align: center;
  padding: 64px 24px 80px;
}
</style>
