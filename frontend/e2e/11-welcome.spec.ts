import { expect, test } from '@playwright/test'

const WIDTHS = [320, 390, 768, 1280]

test('the welcome page never scrolls sideways', async ({ page }) => {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/welcome')
    const measured = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(measured.scrollWidth, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(
      measured.clientWidth + 1,
    )
  }
})

test('the welcome page offers a way in on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 })
  await page.goto('/welcome')

  const signIn = page.getByRole('button', { name: 'Sign in' })
  await expect(signIn).toBeVisible()
  const box = await signIn.boundingBox()
  expect(box?.height ?? 0, 'a tap target must be reachable with a thumb').toBeGreaterThanOrEqual(36)

  await signIn.click()
  await expect(page).toHaveURL(/\/login/)
})

test('the welcome page says what LotScope is before asking for an account', async ({ page }) => {
  await page.goto('/welcome')
  await expect(page.getByText('Philadelphia')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create an account' })).toBeVisible()
})
