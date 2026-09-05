import type { Page } from '@playwright/test'
import { expect } from '@playwright/test'

export const SEEDED = {
  delinquent: { number: 'phl:99900001', address: '1500 E2E FIXTURE WAY' },
  bestMargin: { number: 'phl:99900002', address: '1502 E2E FIXTURE WAY' },
  midMargin: { number: 'phl:99900003', address: '1504 E2E FIXTURE WAY' },
  cityOwned: { number: 'phl:99900005', address: '1508 E2E FIXTURE WAY' },
  longAddress: { number: 'phl:99900006', address: '2909-11 E2E LONG FIXTURE BOULEVARD' },
} as const

export const PRIMARY_DESTINATIONS = ['Analyst', 'Deals', 'Packets'] as const

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

const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? 'http://127.0.0.1:8025'

export async function verificationLink(page: Page, address: string): Promise<string> {
  let body = ''
  await expect
    .poll(
      async () => {
        const found = await page.request.get(`${MAILPIT_URL}/api/v1/search`, {
          params: { query: `to:${address}` },
        })
        const summaries = (await found.json()) as { messages: { ID: string }[] }
        const newest = summaries.messages[0]
        if (newest === undefined) return ''
        const message = await page.request.get(`${MAILPIT_URL}/api/v1/message/${newest.ID}`)
        body = ((await message.json()) as { Text: string }).Text
        return body
      },
      { timeout: 15_000, message: `no verification email arrived for ${address}` },
    )
    .not.toBe('')
  const link = /https?:\/\/\S+\/verify\?token=\S+/.exec(body)?.[0]
  if (link === undefined) throw new Error(`no verification link in the email to ${address}`)
  return link
}

export async function register(page: Page, account: TestAccount): Promise<void> {
  await page.goto('/register')
  await page.getByLabel('Name (optional)').fill(account.fullName)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.locator('[data-test="check-your-email"]')).toBeVisible()

  const link = await verificationLink(page, account.email)
  await page.goto(new URL(link).pathname + new URL(link).search)
  await expect(page).toHaveURL(/\/$/)
}

export async function signIn(page: Page, account: TestAccount): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(account.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/$/)
}

export async function registerAndSettle(page: Page, label: string): Promise<TestAccount> {
  const account = newAccount(label)
  await register(page, account)
  return account
}

export function navItem(page: Page, label: string) {
  return page.getByRole('complementary').getByText(label, { exact: true })
}

export async function openDossier(page: Page, parcelNumber: string): Promise<void> {
  await page.goto(`/lot/${parcelNumber}`)
  const localKey = parcelNumber.split(':')[1] ?? parcelNumber
  await expect(page.getByText(`Parcel ${localKey}`)).toBeVisible()
}
