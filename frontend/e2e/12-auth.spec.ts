import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { newAccount, registerAndSettle, verificationLink } from './support/app'
import type { TestAccount } from './support/app'

async function signInUnverified(page: Page, account: TestAccount): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/)
}

test('an expired token lands on login, not a broken app', async ({ page }) => {
  await registerAndSettle(page, 'expiry')
  await page.goto(`/deals`)
  await expect(page).toHaveURL(/deals/)

  await page.evaluate(() => {
    const dead = { sub: '1', exp: Math.floor(Date.now() / 1000) - 60 }
    const payload = btoa(JSON.stringify(dead))
    localStorage.setItem('lotscope_token', `header.${payload}.signature`)
  })
  await page.reload()
  await page.waitForTimeout(2500)

  await expect(page).toHaveURL(/\/login/)
  expect(await page.evaluate(() => localStorage.getItem('lotscope_token'))).toBeNull()
  expect(page.url()).toContain('redirect=/deals')
})

test('a live session still reaches the app normally', async ({ page }) => {
  await registerAndSettle(page, 'live')
  await page.goto(`/packets`)
  await expect(page).toHaveURL(/packets/)
  await expect(page.getByText('Sale Packets', { exact: true })).toBeVisible()
})

test('an unverified account is told to verify, and the link works once', async ({ page }) => {
  const account = newAccount('verify')
  await page.goto('/register')
  await page.getByLabel('Name (optional)').fill(account.fullName)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.locator('[data-test="check-your-email"]')).toBeVisible()

  await signInUnverified(page, account)
  await page.goto('/deals')
  await expect(page.locator('[data-test="verify-banner"]')).toBeVisible()

  const link = await verificationLink(page, account.email)
  const target = new URL(link)
  await page.goto(target.pathname + target.search)
  await expect(page).toHaveURL(/\/$/)
  await page.goto('/deals')
  await expect(page.locator('[data-test="verify-banner"]')).toHaveCount(0)

  await page.goto(target.pathname + target.search)
  await expect(page.locator('[data-test="verify-failed"]')).toBeVisible()
})
