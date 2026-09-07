import { expect, test, type Page } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

async function withOneDeal(page: Page, label: string): Promise<void> {
  await registerAndSettle(page, label)
  await openDossier(page, SEEDED.midMargin.number)
  await page.getByRole('button', { name: 'Pipeline', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Lead' })).toBeVisible()
  await page.goto('/deals')
}

test('deals is a table with the lot, its stage and its numbers', async ({ page }) => {
  await withOneDeal(page, 'deals-table')

  await expect(page.locator('[data-test="deals-table"]')).toBeVisible()
  const row = page.locator('[data-test="deals-row"]').first()
  await expect(row).toContainText(SEEDED.midMargin.address)
  await expect(row.locator('[data-test="deals-stage"]')).toBeVisible()
  await expect(row.locator('[data-test="deals-mao"]')).toBeVisible()
  await expect(row.locator('[data-test="deals-sale"]')).toBeVisible()
})

test('the stage saves inline', async ({ page }) => {
  await withOneDeal(page, 'deals-stage')

  const stage = page.locator('[data-test="deals-stage"]').first()
  // The dropdown saves on change and the page does not wait for it, so reloading on the
  // next line races the PATCH and cancels it — rarely alone, reliably under load.
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      /\/pipeline\//.test(response.url()) &&
      response.ok(),
  )
  await stage.selectOption('diligence')
  await saved

  // Reload rather than trusting the optimistic update: the point is that it was saved.
  await page.reload()
  await expect(page.locator('[data-test="deals-stage"]').first()).toHaveValue('diligence')
})

test('a selection is handed to the Analyst', async ({ page }) => {
  await withOneDeal(page, 'deals-ask')

  await expect(page.locator('[data-test="deals-ask"]')).toBeDisabled()
  await page.locator('[data-test="deals-select"]').first().check()
  await expect(page.locator('[data-test="deals-ask"]')).toContainText('Ask about 1')

  await page.locator('[data-test="deals-ask"]').click()
  await expect(page.locator('[data-test="analyst-thread"]')).toBeVisible()
})

test('a row opens its lot', async ({ page }) => {
  await withOneDeal(page, 'deals-open')

  await page.locator('[data-test="deals-open"]').first().click()
  await expect(page).toHaveURL(new RegExp(`/lot/`))
})

test('deals is one card per lot at 380px', async ({ page }) => {
  await page.setViewportSize({ width: 380, height: 820 })
  await withOneDeal(page, 'deals-mobile')

  await expect(page.locator('[data-test="deals-row"]').first()).toBeVisible()
  // A table that scrolls sideways on a phone is a table nobody reads.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)

  await expect(page.locator('[data-test="deals-stage"]').first()).toBeVisible()
})

test('a row can produce its offer letter', async ({ page }) => {
  await withOneDeal(page, 'deals-loi')

  await page.locator('[data-test="deals-offer-letter"]').first().click()
  await expect(page.getByText('Generate offer', { exact: true })).toBeVisible()
})
