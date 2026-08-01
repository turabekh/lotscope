import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 5 — the verdict tab shows a screening result and its reasoning', async ({ page }) => {
  await registerAndSettle(page, 'verdict')
  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.getByRole('tab', { name: 'Verdict' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('Screening result')).toBeVisible()
  await expect(page.getByRole('button', { name: /Why this result\?/ })).toBeVisible()
  await expect(page.getByText('Buildability').first()).toBeVisible()
  await expect(page.getByText('Est. land value').first()).toBeVisible()
})

test('flow 5 — the deal tab shows the offer the verdict is built on', async ({ page }) => {
  await registerAndSettle(page, 'verdict-deal')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()

  await expect(page.getByText('Max allowable offer').first()).toBeVisible()
  await expect(page.getByText('Deal analysis').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Show assumptions and formula' })).toBeVisible()
})

test('flow 5 — a parcel with weak economics is not recommended', async ({ page }) => {
  await registerAndSettle(page, 'verdict-weak')
  await openDossier(page, SEEDED.cityOwned.number)

  await expect(page.getByText('Screening result')).toBeVisible()
})
