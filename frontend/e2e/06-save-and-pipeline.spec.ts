import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 7 — saving a parcel puts it on the saved-lots list', async ({ page }) => {
  await registerAndSettle(page, 'save')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('button', { name: 'Save to watchlist' }).click()

  await page.goto(`/lists`)
  await expect(page.getByRole('tab', { name: 'Saved lots' })).toBeVisible()
  await expect(page.getByText(SEEDED.bestMargin.address)).toBeVisible()
})

test('flow 8 — adding a parcel to the pipeline gives it a stage', async ({ page }) => {
  await registerAndSettle(page, 'pipeline')
  await openDossier(page, SEEDED.midMargin.number)

  await page.getByRole('button', { name: 'Pipeline', exact: true }).click()

  await expect(page.getByRole('link', { name: 'Lead' })).toBeVisible()

  await page.goto(`/pipeline`)
  await expect(page.getByText(SEEDED.midMargin.address)).toBeVisible()
})
