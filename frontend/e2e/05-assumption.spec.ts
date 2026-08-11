import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 6 — editing an assumption recomputes the deal', async ({ page }) => {
  await registerAndSettle(page, 'assumption')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await expect(page.locator('[data-test="deal-controls"]')).toBeVisible()

  const acquisition = page.getByRole('spinbutton', { name: 'Acquisition price ($)' })
  await expect(acquisition).toBeVisible()
  await acquisition.fill('40000')
  await page.getByRole('button', { name: 'Recompute', exact: true }).click()

  await expect(page.getByRole('button', { name: 'Reset', exact: true })).toBeEnabled()
})

test('flow 6 — resetting returns the deal to market defaults', async ({ page }) => {
  await registerAndSettle(page, 'assumption-reset')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await expect(page.locator('[data-test="deal-controls"]')).toBeVisible()

  await page.getByRole('spinbutton', { name: 'Target margin (%)' }).fill('45')
  await page.getByRole('button', { name: 'Recompute', exact: true }).click()
  await page.getByRole('button', { name: 'Reset', exact: true }).click()

  await expect(page.getByText('Assumptions: market default')).toBeVisible()
})

test('flow 6 — the deal card carries the whole loop from figure to offer', async ({ page }) => {
  await registerAndSettle(page, 'deal-loop')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()

  const grid = page.locator('[data-test="heatmap"]')
  const construction = page.locator('[data-test="breakdown-construction"]')
  await expect(page.locator('[data-test="deal-mao"]')).toBeVisible()
  await expect(page.locator('[data-test="case-strip"]')).toBeVisible()
  await expect(grid).toBeVisible()

  const gridBefore = await grid.innerText()
  const constructionBefore = await construction.innerText()

  await page.getByRole('spinbutton', { name: 'Construction ($/sqft)' }).fill('100')
  await page.getByRole('button', { name: 'Recompute', exact: true }).click()

  await expect(construction).not.toHaveText(constructionBefore)
  await expect(grid).not.toHaveText(gridBefore)

  await page.locator('[data-test="deal-generate-offer"]').click()
  await expect(page.getByText('Generate offer', { exact: true })).toBeVisible()
})
