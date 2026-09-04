import { expect, test } from '@playwright/test'

import { dismissTour, newAccount, register } from './support/app'

test('flow 2 — a new user completes the tour and is pointed at the buy box', async ({ page }) => {
  await register(page, newAccount('onboarding'))

  await expect(page.getByRole('button', { name: 'Skip' })).toBeVisible()
  await dismissTour(page)

  const prompt = page.locator('[data-test="buy-box-prompt"]')
  await expect(prompt).toBeVisible()
  await prompt.getByRole('link', { name: 'Set it up' }).click()
  await expect(page).toHaveURL(/\/account/)
  await expect(page.locator('[data-test="buy-box-editor"]')).toBeVisible()
})

test('flow 2 — the buy box saves and reads back', async ({ page }) => {
  await register(page, newAccount('onboarding-save'))
  await dismissTour(page)
  await page.goto('/account')

  const editor = page.locator('[data-test="buy-box-editor"]')
  await expect(editor).toBeVisible()

  await editor.locator('[data-test="buy-box-max-bid"]').fill('250000')
  await editor.locator('[data-test="buy-box-target_margin"]').fill('0.3')
  await editor.locator('[data-test="buy-box-zoning"]').fill('rsa-5, cmx-2')
  await editor.locator('[data-test="buy-box-save"]').click()
  await expect(editor.locator('[data-test="buy-box-saved"]')).toBeVisible()

  await page.reload()
  await expect(editor.locator('[data-test="buy-box-max-bid"]')).toHaveValue('250000')
  await expect(editor.locator('[data-test="buy-box-zoning"]')).toHaveValue('RSA-5, CMX-2')
})
