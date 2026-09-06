import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('the diligence button is priced and plainly not purchasable yet', async ({ page }) => {
  await registerAndSettle(page, 'diligence-gate')
  await openDossier(page, SEEDED.delinquent.number)

  const button = page.locator('[data-test="parcel-action-diligence"]')
  await expect(button).toBeVisible()
  await expect(button).toContainText('$199')
  // Billing is unconfigured, so the button says why it will not open rather than
  // sending a buyer to a checkout that cannot take their money.
  await expect(button).toBeDisabled()
})
