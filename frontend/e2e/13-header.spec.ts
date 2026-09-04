import { expect, test } from '@playwright/test'

import { registerAndSettle } from './support/app'

test('search opens a usable field on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'header')
  await page.goto(`/home`)

  await page.locator('[data-test="global-search-open"]').click()

  const field = page.getByPlaceholder('Search address, owner, or parcel #')
  await expect(field).toBeVisible()
  const box = await field.boundingBox()
  expect(box?.width ?? 0).toBeGreaterThan(240)
})

test('the flagship market needs no badge in the phone header', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'header-badge')
  await page.goto(`/home`)

  await expect(page.locator('[data-test="active-market-status"]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Switch market' })).toContainText('PHL')
})
