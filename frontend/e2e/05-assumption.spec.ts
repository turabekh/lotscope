import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 6 — editing an assumption recomputes the deal', async ({ page }) => {
  await registerAndSettle(page, 'assumption')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await page.getByRole('button', { name: /Model a scenario/ }).click()

  const acquisition = page.getByRole('spinbutton', { name: 'Acquisition price ($)' })
  await expect(acquisition).toBeVisible()
  await acquisition.fill('40000')
  await page.getByRole('button', { name: 'Recompute' }).click()

  await expect(page.getByRole('button', { name: 'Reset' })).toBeEnabled()
})

test('flow 6 — resetting returns the deal to market defaults', async ({ page }) => {
  await registerAndSettle(page, 'assumption-reset')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await page.getByRole('button', { name: /Model a scenario/ }).click()

  await page.getByRole('spinbutton', { name: 'Target margin (%)' }).fill('45')
  await page.getByRole('button', { name: 'Recompute' }).click()
  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.getByText('Assumptions: market default')).toBeVisible()
})
