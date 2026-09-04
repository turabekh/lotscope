import { expect, test } from '@playwright/test'
import { registerAndSettle } from './support/app'

test('an expired token lands on login, not a broken app', async ({ page }) => {
  await registerAndSettle(page, 'expiry')
  await page.goto(`/pipeline`)
  await expect(page).toHaveURL(/pipeline/)

  await page.evaluate(() => {
    const dead = { sub: '1', exp: Math.floor(Date.now() / 1000) - 60 }
    const payload = btoa(JSON.stringify(dead))
    localStorage.setItem('lotscope_token', `header.${payload}.signature`)
  })
  await page.reload()
  await page.waitForTimeout(2500)

  await expect(page).toHaveURL(/\/login/)
  expect(await page.evaluate(() => localStorage.getItem('lotscope_token'))).toBeNull()
  expect(page.url()).toContain('redirect=/pipeline')
})

test('a live session still reaches the app normally', async ({ page }) => {
  await registerAndSettle(page, 'live')
  await page.goto(`/lists`)
  await expect(page).toHaveURL(/lists/)
  await expect(page.getByRole('tab', { name: 'Saved lots' })).toBeVisible()
})
