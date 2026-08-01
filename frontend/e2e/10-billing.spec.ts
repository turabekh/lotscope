import { test } from '@playwright/test'

const STRIPE_BLOCKED =
  'Stripe credentials are not configured (LR-B-030); flows 10 and 11 are unbuilt'

test.skip('flow 10 — a user can start checkout', () => {
  throw new Error(STRIPE_BLOCKED)
})

test.skip('flow 11 — a user can upgrade a plan', () => {
  throw new Error(STRIPE_BLOCKED)
})
