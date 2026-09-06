import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 14 — the core path works on a phone viewport', async ({ page }) => {
  await registerAndSettle(page, 'mobile')

  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.getByText('Parcel 99900002')).toBeVisible()
  await expect(page.getByText('Screening result')).toBeVisible()
  await expect(page.locator('[data-test="deal-hero"]')).toBeVisible()
  await expect(page.locator('[data-test="deal-mao"]')).toBeVisible()
})
