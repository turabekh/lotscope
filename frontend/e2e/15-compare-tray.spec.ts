import { expect, test } from '@playwright/test'

import { MARKET_SLUG, registerAndSettle, SEEDED } from './support/app'

test('the tray says what is missing before it lets you compare', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-one')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const tray = page.getByRole('region', { name: 'Compare tray' })
  await expect(tray).toContainText('1 of 4 selected')
  await expect(tray).toContainText('Add one more lot')
  await expect(page.locator('[data-test="compare-open"]')).toBeDisabled()
})

test('the tray names the lot by address, not by parcel id', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-label')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const chip = page.locator(`[data-test="compare-chip-${SEEDED.bestMargin.number}"]`)
  await expect(chip).toContainText(SEEDED.bestMargin.address)
  await expect(chip).not.toContainText('phl:')
})

test('a second lot makes compare available', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-two')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.midMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const tray = page.getByRole('region', { name: 'Compare tray' })
  await expect(tray).toContainText('2 of 4 selected')
  await expect(page.locator('[data-test="compare-open"]')).toBeEnabled()
})
