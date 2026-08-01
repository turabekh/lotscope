import { expect, test } from '@playwright/test'

import { MARKET_SLUG, registerAndSettle, SEEDED } from './support/app'

test('the tray says what is missing before it lets you compare', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-one')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const tray = page.getByRole('region', { name: 'Compare tray' })
  await expect(tray).toContainText('1 of 4 selected')
  await expect(tray).toContainText('Add one more lot')
  await expect(page.locator('[data-test="compare-open"]')).toBeDisabled()
})

test('the tray names the lot by address, not by parcel id', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-label')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const chip = page.locator(`[data-test="compare-chip-${SEEDED.bestMargin.number}"]`)
  await expect(chip).toContainText(SEEDED.bestMargin.address)
  await expect(chip).not.toContainText('phl:')
})

test('a second lot makes compare available', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'tray-two')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.midMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()

  const tray = page.getByRole('region', { name: 'Compare tray' })
  await expect(tray).toContainText('2 of 4 selected')
  await expect(page.locator('[data-test="compare-open"]')).toBeEnabled()
})

async function selectTwo(page: import('@playwright/test').Page): Promise<void> {
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.midMargin.number}`)
  await page.locator('[data-test="parcel-action-compare"]').click()
}

test('two lots fit the phone without sideways scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'table-two')
  await selectTwo(page)
  await page.locator('[data-test="compare-open"]').click()

  await expect(page.getByText('Compare lots')).toBeVisible()
  const measured = await page.evaluate(() => {
    const wrap = document.querySelector('.compare-table') as HTMLElement | null
    return { scrollWidth: wrap?.scrollWidth ?? 0, clientWidth: wrap?.clientWidth ?? 0 }
  })
  expect(measured.scrollWidth).toBeLessThanOrEqual(measured.clientWidth + 1)
})

test('the metric column stays readable instead of values sliding under it', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'table-sticky')
  await selectTwo(page)
  await page.locator('[data-test="compare-open"]').click()

  const label = page.locator('td.metric-col').first()
  await expect(label).toBeVisible()
  const styles = await label.evaluate((node) => {
    const computed = getComputedStyle(node)
    return {
      position: computed.position,
      zIndex: computed.zIndex,
      background: computed.backgroundColor,
    }
  })
  expect(styles.position).toBe('sticky')
  expect(Number(styles.zIndex)).toBeGreaterThan(0)
  expect(styles.background).not.toBe('rgba(0, 0, 0, 0)')
})
