import { expect, test } from '@playwright/test'

import { registerAndSettle } from './support/app'

test('search opens a usable field on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'header')
  await page.goto(`/`)

  await page.locator('[data-test="global-search-open"]').click()

  const field = page.getByPlaceholder('Search address, owner, or parcel #')
  await expect(field).toBeVisible()
  const box = await field.boundingBox()
  expect(box?.width ?? 0).toBeGreaterThan(240)
})
