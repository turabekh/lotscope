import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flows 3 and 4 — search by address reaches the dossier', async ({ page }) => {
  await registerAndSettle(page, 'search')

  await page.getByPlaceholder('Search address, owner, or parcel #').fill('1502 E2E FIXTURE')

  const suggestion = page.getByText(SEEDED.bestMargin.address).first()
  await expect(suggestion).toBeVisible()
  await suggestion.click()

  await expect(page).toHaveURL(new RegExp(`/lot/`))
  await expect(page.getByText('Parcel 99900002')).toBeVisible()
})

test('flow 4 — a dossier opens directly by parcel number', async ({ page }) => {
  await registerAndSettle(page, 'dossier')

  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.getByRole('button', { name: SEEDED.bestMargin.address })).toBeVisible()
  // One page now: every section is present, and the nav lists them.
  for (const section of ['verdict', 'deeds', 'violations', 'comps', 'neighbors']) {
    await expect(page.locator(`#${section}`)).toHaveCount(1)
  }
  await expect(page.locator('[data-test="lot-section-nav"]')).toBeVisible()
})

test('the zoning section affirms what was checked, not just what was found', async ({ page }) => {
  await registerAndSettle(page, 'landtab')

  await openDossier(page, SEEDED.bestMargin.number)
  await page.locator('[data-test="lot-nav-zoning-overlays"]').click()

  await expect(page.getByText('Not in a designated historic district')).toBeVisible()
  await expect(page.getByText('Not designated')).toBeVisible()
  await expect(page.getByText('could not be checked')).toHaveCount(0)
  await expect(page.getByText('Buyable neighbors')).toHaveCount(0)
})
