import type { Page } from '@playwright/test'
import { expect } from '@playwright/test'

export const MARKET_SLUG = 'philadelphia'

export const SEEDED = {
  delinquent: { number: 'phl:99900001', address: '1500 E2E FIXTURE WAY' },
  bestMargin: { number: 'phl:99900002', address: '1502 E2E FIXTURE WAY' },
  midMargin: { number: 'phl:99900003', address: '1504 E2E FIXTURE WAY' },
  cityOwned: { number: 'phl:99900005', address: '1508 E2E FIXTURE WAY' },
} as const

export const PRIMARY_DESTINATIONS = ['Home', 'Find lots', 'Leads', 'Pipeline', 'Lists'] as const

export interface TestAccount {
  email: string
  password: string
  fullName: string
}

let sequence = 0

export function newAccount(label: string): TestAccount {
  sequence += 1
  const unique = `${process.pid}-${Date.now()}-${sequence}`
  return {
    email: `e2e-${label}-${unique}@lotscope.test`,
    password: 'e2e-password-1234',
    fullName: `E2E ${label}`,
  }
}

export async function register(page: Page, account: TestAccount): Promise<void> {
  await page.goto('/register')
  await page.getByLabel('Name (optional)').fill(account.fullName)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(new RegExp(`/${MARKET_SLUG}/home`))
}

export async function signIn(page: Page, account: TestAccount): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(new RegExp(`/${MARKET_SLUG}/`))
}

export async function dismissTour(page: Page): Promise<void> {
  const skip = page.getByRole('button', { name: 'Skip' })
  try {
    await skip.waitFor({ state: 'visible', timeout: 8_000 })
  } catch {
    return
  }
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/auth/onboarded') && response.ok()),
    skip.click(),
  ])
  await expect(page.locator('.q-dialog__backdrop')).toHaveCount(0)
}

export async function registerAndSettle(page: Page, label: string): Promise<TestAccount> {
  const account = newAccount(label)
  await register(page, account)
  await dismissTour(page)
  return account
}

export function navItem(page: Page, label: string) {
  return page.getByRole('complementary').getByText(label, { exact: true })
}

export async function openDossier(page: Page, parcelNumber: string): Promise<void> {
  await page.goto(`/parcel/${MARKET_SLUG}/${parcelNumber}`)
  await dismissTour(page)
  const localKey = parcelNumber.split(':')[1] ?? parcelNumber
  await expect(page.getByText(`Parcel ${localKey}`)).toBeVisible()
}
