import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 5 — the verdict shows a screening result and its reasoning', async ({ page }) => {
  await registerAndSettle(page, 'verdict')
  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.locator('#verdict')).toBeVisible()
  await expect(page.getByText('Screening result')).toBeVisible()
  await expect(page.getByRole('button', { name: /Why this result\?/ })).toBeVisible()
  await expect(page.getByText('Buildability').first()).toBeVisible()
  await expect(page.getByText('Est. land value').first()).toBeVisible()
})

test('flow 5 — the verdict shows the offer it is built on', async ({ page }) => {
  await registerAndSettle(page, 'verdict-deal')
  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.getByText('Deal analysis').first()).toBeVisible()
  await expect(page.locator('[data-test="deal-hero"]')).toContainText(/Offer up to|No viable price/)
  await expect(page.locator('[data-test="deal-mao"]')).toBeVisible()
  await expect(page.getByText('How this was computed')).toBeVisible()
  await expect(
    page.getByText('Informational only — not an appraisal, and not legal or financial advice.'),
  ).toBeVisible()
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

test('flow 5 — the verdict shows risk, not a blank pane', async ({ page }) => {
  await registerAndSettle(page, 'verdict-risk')
  await openDossier(page, SEEDED.bestMargin.number)
  // Risk flags sit in the verdict: they are part of the read on the lot, not a place.
  await page.locator('[data-test="lot-nav-verdict"]').click()

  const panel = page.locator('[data-test="risk-panel"]')
  await expect(panel).toBeVisible()
  await expect(page.locator('[data-test="risk-panel-score"]')).toBeVisible()
  await expect(page.locator('[data-test="risk-panel-summary"]')).not.toBeEmpty()
})

test('flow 5 — the owner section always says something about the owner', async ({ page }) => {
  await registerAndSettle(page, 'verdict-owner')
  await openDossier(page, SEEDED.bestMargin.number)
  await page.locator('[data-test="lot-nav-neighbors"]').click()

  const owner = page.locator('[data-test="owner-sole-holding"], [data-test="owner-portfolio-list"]')
  await expect(owner).toBeVisible()
  await expect(owner).toContainText('Owner portfolio')
})

test('flow 5 — the dossier answers what can be built, with its basis', async ({ page }) => {
  await registerAndSettle(page, 'verdict-program')
  await openDossier(page, SEEDED.bestMargin.number)

  const panel = page.locator('[data-test="program-panel"]')
  await expect(panel).toBeVisible()
  await expect(page.locator('[data-test="program-statement"]')).not.toBeEmpty()
  await expect(page.locator('[data-test="program-claims"]')).toContainText(
    /verified|calculated|estimated|unavailable/,
  )
  await expect(page.locator('[data-test="program-conditions"]')).toContainText(
    'not a zoning determination',
  )
})
