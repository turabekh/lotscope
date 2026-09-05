import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 7 — saving a parcel is reflected on the lot itself', async ({ page }) => {
  await registerAndSettle(page, 'save')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('button', { name: 'Save to watchlist' }).click()

  // The Lists page is gone; the lot is the record of what you saved.
  // The button's accessible name is its aria-label, which flips once it is saved.
  await expect(page.getByRole('button', { name: 'Remove from watchlist' })).toBeVisible()
})

test('flow 8 — adding a parcel to the pipeline gives it a stage', async ({ page }) => {
  await registerAndSettle(page, 'pipeline')
  await openDossier(page, SEEDED.midMargin.number)

  await page.getByRole('button', { name: 'Pipeline', exact: true }).click()

  await expect(page.getByRole('link', { name: 'Lead' })).toBeVisible()

  await page.goto(`/deals`)
  await expect(page.getByText(SEEDED.midMargin.address)).toBeVisible()
})
