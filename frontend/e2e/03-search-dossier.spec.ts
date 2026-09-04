import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flows 3 and 4 — search by address reaches the dossier', async ({ page }) => {
  await registerAndSettle(page, 'search')

  await page.getByPlaceholder('Search address, owner, or parcel #').fill('1502 E2E FIXTURE')

  const suggestion = page.getByText(SEEDED.bestMargin.address).first()
  await expect(suggestion).toBeVisible()
  await suggestion.click()

  await expect(page).toHaveURL(new RegExp(`/parcel/`))
  await expect(page.getByText('Parcel 99900002')).toBeVisible()
})

test('flow 4 — a dossier opens directly by parcel number', async ({ page }) => {
  await registerAndSettle(page, 'dossier')

  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.getByRole('button', { name: SEEDED.bestMargin.address })).toBeVisible()
  for (const tab of ['Verdict', 'Deal', 'Land', 'Risk', 'Docs']) {
    await expect(page.getByRole('tab', { name: tab })).toBeVisible()
  }
})

test('the Land tab affirms what was checked, not just what was found', async ({ page }) => {
  await registerAndSettle(page, 'landtab')

  await openDossier(page, SEEDED.bestMargin.number)
  await page.getByRole('tab', { name: 'Land' }).click()

  await expect(page.getByText('Not in a designated historic district')).toBeVisible()
  await expect(page.getByText('Not designated')).toBeVisible()
  await expect(page.getByText('could not be checked')).toHaveCount(0)
  await expect(page.getByText('Buyable neighbors')).toHaveCount(0)
})
