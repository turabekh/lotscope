import { expect, test } from '@playwright/test'

const WIDTHS = [320, 390, 768, 1280]

test('the landing page never scrolls sideways', async ({ page }) => {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/')
    const measured = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(measured.scrollWidth, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(
      measured.clientWidth + 1,
    )
  }
})

test('the landing page leads with one full-width call to action on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 })
  await page.goto('/')

  const cta = page.getByRole('link', { name: 'Create a free account' })
  await expect(cta).toBeVisible()
  const box = await cta.boundingBox()
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
  expect(box?.width ?? 0).toBeGreaterThan(280)

  await expect(page.getByText('Base district · 3 units')).toBeVisible()
})
