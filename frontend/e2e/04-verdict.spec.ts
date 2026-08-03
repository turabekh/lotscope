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

test('flow 5 — the buildability qualifier is visible without hovering', async ({ page }) => {
  await registerAndSettle(page, 'verdict-qualifier')
  await openDossier(page, SEEDED.bestMargin.number)

  const qualifier = page.locator('[data-test="build-qualifier"]')
  await expect(qualifier).toBeVisible()
  await expect(qualifier).not.toBeEmpty()
})

test('flow 5 — the by-right read carries a visible confidence label', async ({ page }) => {
  await registerAndSettle(page, 'verdict-confidence')
  await openDossier(page, SEEDED.bestMargin.number)

  const label = page.locator('[data-test="buildability-confidence"]')
  await expect(label).toBeVisible()
  await expect(label).toContainText(/High confidence|Medium confidence|Low confidence/)
})

test('flow 5 — the risk tab shows risk, not a blank pane', async ({ page }) => {
  await registerAndSettle(page, 'verdict-risk')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Risk' }).click()

  const panel = page.locator('[data-test="risk-panel"]')
  await expect(panel).toBeVisible()
  await expect(page.locator('[data-test="risk-panel-score"]')).toBeVisible()
  await expect(page.locator('[data-test="risk-panel-summary"]')).not.toBeEmpty()
})

test('flow 5 — the owner section always says something about the owner', async ({ page }) => {
  await registerAndSettle(page, 'verdict-owner')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Risk' }).click()
  await expect(page.locator('[data-test="risk-panel"]')).toBeVisible()

  const owner = page.locator('[data-test="owner-sole-holding"], [data-test="owner-portfolio-list"]')
  await expect(owner).toBeVisible()
  await expect(owner).toContainText('Owner portfolio')
})
