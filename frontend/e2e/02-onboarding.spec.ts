import { expect, test } from '@playwright/test'

import { dismissTour, newAccount, register } from './support/app'

test('flow 2 — a new user completes the tour and sets a buy box', async ({ page }) => {
  await register(page, newAccount('onboarding'))

  await expect(page.getByRole('button', { name: 'Skip' })).toBeVisible()
  await dismissTour(page)

  const buyBox = page.locator('[data-test="buy-box-onboarding"]')
  await expect(buyBox).toBeVisible()

  await page.getByRole('spinbutton', { name: 'Most you would pay' }).fill('250000')
  await page.getByRole('spinbutton', { name: 'Target margin' }).fill('20')
  await buyBox.getByRole('button', { name: 'Save and show matches' }).click()

  const results = buyBox.locator('[data-test="buy-box-results"]')
  await expect(results).toBeVisible()
  await expect(results).toContainText(/matching lot/)
})

test('flow 2 — the buy box refuses to submit with no criterion set', async ({ page }) => {
  await register(page, newAccount('onboarding-empty'))
  await dismissTour(page)

  const buyBox = page.locator('[data-test="buy-box-onboarding"]')
  await expect(buyBox.getByRole('button', { name: 'Save and show matches' })).toBeDisabled()
})
