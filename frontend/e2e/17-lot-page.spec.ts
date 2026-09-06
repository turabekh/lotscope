import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('a lot shows where a fact came from', async ({ page }) => {
  await registerAndSettle(page, 'lot-showme')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Land' }).click()

  // The owner is read from the assessment record, and the reader can open that row.
  const owner = page.locator('[data-test="fact-owner"]')
  await expect(owner).toBeVisible()
  const link = owner.locator('[data-test="show-me-external"]')
  await expect(link).toHaveAttribute('target', '_blank')
  expect(await link.getAttribute('href')).toContain('opa_properties_public')
})

test('a fact with no public page names our source and its as-of', async ({ page }) => {
  await registerAndSettle(page, 'lot-stored')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Land' }).click()

  const area = page.locator('[data-test="fact-lot-area"]')
  await area.locator('[data-test="show-me"]').click()

  const pop = area.locator('[data-test="show-me-stored"]')
  await expect(pop).toBeVisible()
  await expect(pop).toContainText('No public page for this')
})

test('the lot hands itself to the Analyst with the parcel already in context', async ({ page }) => {
  await registerAndSettle(page, 'lot-ask')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.locator('[data-test="parcel-action-ask"]').click()

  await expect(page).toHaveURL(/\/$|about=/)
  // The Analyst opens the conversation itself rather than making the buyer retype it.
  await expect(page.locator('[data-test="analyst-thread"]')).toBeVisible()
})

test('diligence is offered but plainly not available yet', async ({ page }) => {
  await registerAndSettle(page, 'lot-diligence')
  await openDossier(page, SEEDED.bestMargin.number)

  const button = page.locator('[data-test="parcel-action-diligence"]')
  await expect(button).toBeVisible()
  await expect(button).toBeDisabled()
  await expect(button).toContainText('$199')
})

test('editing an assumption is applied to the deal', async ({ page }) => {
  await registerAndSettle(page, 'lot-assumption')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await expect(page.locator('[data-test="deal-controls"]')).toBeVisible()

  await page.getByRole('spinbutton', { name: 'Target margin (%)' }).fill('35')
  await page.getByRole('button', { name: 'Recompute', exact: true }).click()

  // That the offer moves with the margin is arithmetic, and it is asserted in
  // deal/tests/test_analysis.py where it holds for every fixture. What the browser can
  // prove is that the control reaches the deal at all: the seeded lot is infeasible, so
  // its price reads the same either way and asserting on it would prove nothing.
  // Reset becoming available is the signal that an override is in force. The
  // "Assumptions:" line reports where the cost figures came from, not whether the buyer
  // changed anything, so it correctly stays as it was.
  await expect(page.getByRole('button', { name: 'Reset', exact: true })).toBeEnabled()
})
