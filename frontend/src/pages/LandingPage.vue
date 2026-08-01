<script setup lang="ts">
import { storeToRefs } from 'pinia'

import HeroShowcase from '@/components/HeroShowcase.vue'
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
    text: 'By-right units, height and setbacks under Title 14 — or a clear “needs a variance”.',
  },
  {
    icon: 'payments',
    title: 'Recorded-sale valuation',
    text: 'Land value from real nearby deeds, with a confidence signal.',
  },
  {
    icon: 'warning_amber',
    title: 'Risk flags',
    text: 'Liens, L&I violations, flood zones and city ownership, per parcel.',
  },
  {
    icon: 'forum',
    title: 'Ask the parcel',
    text: 'Cited answers drawn from Philadelphia’s zoning code.',
  },
]
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header class="site-header">
      <q-toolbar class="toolbar">
        <q-icon name="location_city" size="24px" class="q-mr-sm" />
        <q-toolbar-title class="brand">
          LotScope <span class="text-weight-light">PHL</span>
        </q-toolbar-title>
        <q-btn
          v-if="isAuthenticated"
          unelevated
          dense
          color="white"
          text-color="indigo-10"
          no-caps
          label="Open the map"
          :to="{ name: 'explore', params: { market: market.active } }"
        />
        <q-btn v-else flat dense no-caps label="Sign in" :to="{ name: 'login' }" />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page>
        <section class="hero">
          <div class="hero-inner">
            <div class="eyebrow">Philadelphia parcel intelligence</div>
            <h1 class="hero-title">Know what can be built on any Philadelphia lot.</h1>
            <p class="hero-sub">
              Buildability, value and risk for every parcel — with the reasoning shown and the
              sources cited.
            </p>

            <div class="hero-actions">
              <q-btn
                v-if="isAuthenticated"
                unelevated
                size="lg"
                color="amber-7"
                text-color="dark"
                no-caps
                icon="map"
                label="Open the map"
                class="cta-primary"
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
                  class="cta-primary"
                  :to="{ name: 'register' }"
                />
                <q-btn
                  flat
                  no-caps
                  class="cta-secondary"
                  label="or sign in"
                  :to="{ name: 'login' }"
                />
              </template>
            </div>
            <div class="hero-note">Free plan: 4 parcels and 10 AI questions a day.</div>

            <HeroShowcase class="preview" />
          </div>
        </section>

        <section class="features">
          <ul class="feature-list">
            <li v-for="f in features" :key="f.title" class="feature">
              <q-icon :name="f.icon" size="22px" class="feature-icon" />
              <div>
                <div class="feature-title">{{ f.title }}</div>
                <div class="feature-text">{{ f.text }}</div>
              </div>
            </li>
          </ul>
        </section>

        <section class="pricing-section">
          <div class="pricing-inner">
            <div class="pricing-head">
              <div class="eyebrow eyebrow-dark">Pricing</div>
              <h2 class="section-title">Start free. Upgrade when you need more.</h2>
            </div>
            <PricingPlans />
          </div>
        </section>

        <section class="cta">
          <h2 class="section-title">Start exploring Philadelphia lots</h2>
          <q-btn
            class="cta-primary q-mt-md"
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
          <p class="disclaimer">
            Informational only — not legal, financial or real-estate advice. City data is provided
            as-is.
          </p>
        </section>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.site-header {
  background: #2a2c5c;
  color: #fff;
}
body.body--dark .site-header {
  background: #141a2c;
}
.toolbar {
  min-height: 52px;
}
.brand {
  font-weight: 700;
  font-size: 17px;
}

.hero {
  color: #fff;
  background:
    radial-gradient(120% 120% at 12% 0%, rgba(99, 102, 241, 0.5) 0%, transparent 58%),
    linear-gradient(150deg, #2a2c5c, #47306f);
  padding: 28px 20px 36px;
}
body.body--dark .hero {
  background:
    radial-gradient(120% 120% at 12% 0%, rgba(129, 140, 248, 0.24) 0%, transparent 58%),
    linear-gradient(150deg, #151a2e, #2a2148);
}
.hero-inner {
  max-width: 1080px;
  margin: 0 auto;
}
.eyebrow {
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: #fcd34d;
}
.eyebrow-dark {
  color: var(--lot-accent);
}
.hero-title {
  font-size: clamp(27px, 7vw, 46px);
  line-height: 1.12;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 10px 0 10px;
}
.hero-sub {
  font-size: clamp(14.5px, 4vw, 18px);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.86);
  max-width: 560px;
  margin: 0;
}
.hero-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  margin-top: 18px;
}
.cta-primary {
  font-weight: 700;
  border-radius: 12px;
}
.cta-secondary {
  color: rgba(255, 255, 255, 0.9);
}
.hero-note {
  margin-top: 10px;
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.75);
}

.preview {
  margin-top: 22px;
}
.features {
  padding: 26px 20px;
  background: var(--lot-bg);
}
.feature-list {
  list-style: none;
  margin: 0 auto;
  padding: 0;
  max-width: 1080px;
  display: grid;
  gap: 14px;
}
.feature {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.feature-icon {
  color: var(--q-primary);
  flex: none;
  margin-top: 2px;
}
.feature-title {
  font-weight: 700;
  font-size: 14.5px;
}
.feature-text {
  font-size: 13px;
  line-height: 1.45;
  color: var(--lot-muted, #6b7280);
  margin-top: 2px;
}

.pricing-section {
  padding: 30px 0 34px;
  background: var(--lot-surface);
}
.pricing-inner {
  max-width: 1080px;
  margin: 0 auto;
}
.pricing-head {
  text-align: center;
  padding: 0 20px;
  margin-bottom: 16px;
}
.section-title {
  font-size: clamp(20px, 5.4vw, 30px);
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.2;
  margin: 6px 0 0;
}
.cta {
  text-align: center;
  padding: 34px 20px 44px;
}
.disclaimer {
  margin: 16px auto 0;
  max-width: 520px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--lot-muted, #6b7280);
}

@media (min-width: 720px) {
  .hero {
    padding: 56px 24px 64px;
  }
  .hero-inner {
    display: grid;
    grid-template-columns: 1.05fr 0.95fr;
    column-gap: 40px;
    align-items: center;
  }
  .eyebrow,
  .hero-title,
  .hero-sub,
  .hero-actions,
  .hero-note {
    grid-column: 1;
  }
  .hero-actions {
    flex-direction: row;
    align-items: center;
    gap: 10px;
  }
  .cta-primary {
    flex: none;
  }
  .preview {
    grid-column: 2;
    grid-row: 1 / span 5;
    margin-top: 0;
    justify-self: end;
    width: 100%;
  }
  .features {
    padding: 44px 24px;
  }
  .feature-list {
    grid-template-columns: repeat(2, 1fr);
    gap: 22px 32px;
  }
  .pricing-section {
    padding: 52px 0 56px;
  }
  .cta {
    padding: 52px 24px 64px;
  }
}

@media (min-width: 1024px) {
  .feature-list {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
