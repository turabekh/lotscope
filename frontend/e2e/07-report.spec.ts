import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('flow 12 — a dossier report downloads', async ({ page }) => {
  await registerAndSettle(page, 'report')
  await openDossier(page, SEEDED.bestMargin.number)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download PDF dossier' }).click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toMatch(/\.pdf$/)
})
