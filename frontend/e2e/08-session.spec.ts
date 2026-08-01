import { expect, test } from '@playwright/test'

import { dismissTour, MARKET_SLUG, newAccount, register, signIn } from './support/app'

test('flow 13 — a user can log out and sign back in', async ({ page }) => {
  const account = newAccount('session')
  await register(page, account)
  await dismissTour(page)

  await page.goto('/account')
  await page.getByRole('button', { name: 'Sign out' }).click()

  await page.goto(`/${MARKET_SLUG}/home`)
  await expect(page).toHaveURL(/\/login/)

  await signIn(page, account)
  await expect(page).toHaveURL(new RegExp(`/${MARKET_SLUG}/`))
})
