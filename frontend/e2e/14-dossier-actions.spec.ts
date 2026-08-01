import { expect, test } from '@playwright/test'

import { MARKET_SLUG, registerAndSettle, SEEDED } from './support/app'

const ACTIONS = ['save', 'compare', 'pipeline', 'report']

test('every parcel action is labelled and tappable on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'actions')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)

  for (const action of ACTIONS) {
    const button = page.locator(`[data-test="parcel-action-${action}"]`)
    await expect(button).toBeVisible()
    const box = await button.boundingBox()
    expect(box?.height ?? 0, `${action} is too small to tap`).toBeGreaterThanOrEqual(44)
  }

  await expect(page.locator('[data-test="parcel-action-save"]')).toContainText('Save')
  await expect(page.locator('[data-test="parcel-action-compare"]')).toContainText('Compare')
  await expect(page.locator('[data-test="parcel-action-report"]')).toContainText('Report')
})

test('saving and comparing announce themselves', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'actions-state')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.midMargin.number}`)

  await page.locator('[data-test="parcel-action-save"]').click()
  await expect(page.locator('[data-test="parcel-action-save"]')).toContainText('Saved')

  await page.locator('[data-test="parcel-action-compare"]').click()
  await expect(page.locator('[data-test="parcel-action-compare"]')).toContainText('Comparing')
})

test('the actions stay on one row beside the address on a desktop', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await registerAndSettle(page, 'actions-desktop')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)

  const save = await page.locator('[data-test="parcel-action-save"]').boundingBox()
  const report = await page.locator('[data-test="parcel-action-report"]').boundingBox()
  expect(save?.y ?? 0).toBeCloseTo(report?.y ?? 0, 0)
})

test('the back control keeps its row for the actions rather than a word', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'actions-back')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)

  const back = page.locator('[data-test="dossier-back"]')
  await expect(back).toBeVisible()
  await expect(page.getByText('Back', { exact: true })).toHaveCount(0)

  const backBox = await back.boundingBox()
  const saveBox = await page.locator('[data-test="parcel-action-save"]').boundingBox()
  const backCentre = (backBox?.y ?? 0) + (backBox?.height ?? 0) / 2
  const saveCentre = (saveBox?.y ?? 0) + (saveBox?.height ?? 0) / 2
  expect(Math.abs(backCentre - saveCentre), 'back is not on the action row').toBeLessThan(4)
})

test('a long address is not squeezed by the actions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'actions-long')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.longAddress.number}`)

  const address = page.getByText(SEEDED.longAddress.address).first()
  await expect(address).toBeVisible()
  const box = await address.boundingBox()
  expect(box?.height ?? 99, 'the address wrapped again').toBeLessThan(32)
})

test('a laptop gets the map beside the dossier, not dead space', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await registerAndSettle(page, 'split-desktop')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)

  const map = page.locator('[data-test="dossier-map"]')
  await expect(map).toBeVisible()

  const mapBox = await map.boundingBox()
  const frameBox = await page.locator('.dossier-frame').boundingBox()
  expect(mapBox?.width ?? 0, 'the map should take the free width').toBeGreaterThan(500)
  expect(frameBox?.width ?? 0).toBeGreaterThan(380)
  expect((mapBox?.width ?? 0) + (frameBox?.width ?? 0)).toBeGreaterThan(1100)
})

test('a phone keeps the dossier full width with no map', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await registerAndSettle(page, 'split-mobile')
  await page.goto(`/parcel/${MARKET_SLUG}/${SEEDED.bestMargin.number}`)

  await expect(page.locator('[data-test="dossier-map"]')).toHaveCount(0)
  const frame = await page.locator('.dossier-frame').boundingBox()
  expect(frame?.width ?? 0).toBeGreaterThan(360)
})
