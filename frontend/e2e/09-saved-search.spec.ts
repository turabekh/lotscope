import { expect, test } from '@playwright/test'

import { registerAndSettle } from './support/app'

test('flow 9 — a user can create a saved search', async ({ page }) => {
  await registerAndSettle(page, 'saved-search')

  await page.goto(`/lists`)
  await page.getByRole('tab', { name: 'Saved searches' }).click()

  await expect(page.getByText('No saved searches yet')).toBeVisible()
  await page.getByRole('button', { name: 'New search' }).click()

  await expect(page.getByText('New saved search')).toBeVisible()
  await page.getByLabel('Name', { exact: true }).fill('South Broad vacant lots')
  await page.getByLabel('ZIP').fill('19147')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('South Broad vacant lots')).toBeVisible()
})
