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

  const showcase = page.locator('[data-test="hero-showcase"]')
  await expect(showcase).toBeVisible()
  await showcase.locator('[data-test="showcase-tab-deal"]').click()
  await expect(showcase.locator('[data-test="showcase-tab-deal"]')).toHaveAttribute(
    'aria-selected',
    'true',
  )
})

test('landing controls stay legible in dark mode', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/')

  const luminanceOf = (locator: import('@playwright/test').Locator) =>
    locator.evaluate((node) => {
      const parsed = getComputedStyle(node).color.match(/\d+(\.\d+)?/g) ?? []
      const [r, g, b] = parsed.slice(0, 3).map((value) => Number(value) / 255)
      const channel = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
      return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
    })

  const outlineCta = page.getByRole('link', { name: /Get started/ }).first()
  await expect(outlineCta).toBeVisible()
  expect(await luminanceOf(outlineCta)).toBeGreaterThan(0.2)
})
