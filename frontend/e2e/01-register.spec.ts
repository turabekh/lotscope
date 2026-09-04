import { expect, test } from '@playwright/test'

import { newAccount, navItem, PRIMARY_DESTINATIONS, register } from './support/app'

test('flow 1 — a new visitor can register and lands in the app', async ({ page }) => {
  const account = newAccount('register')

  await register(page, account)

  await expect(page).toHaveURL(new RegExp(`/home`))
  for (const destination of PRIMARY_DESTINATIONS) {
    await expect(navItem(page, destination)).toBeVisible()
  }
})

test('flow 1 — registration keeps the visitor on the form when it fails', async ({ page }) => {
  const account = newAccount('short-password')

  await page.goto('/register')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill('short')
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/register/)
})
