import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('a lot shows where a fact came from', async ({ page }) => {
  await registerAndSettle(page, 'lot-showme')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Land' }).click()

  // The owner is read from the assessment record, and the reader can open that row.
  const owner = page.locator('[data-test="fact-owner"]')
  await expect(owner).toBeVisible()
  const link = owner.locator('[data-test="show-me-external"]')
  await expect(link).toHaveAttribute('target', '_blank')
  expect(await link.getAttribute('href')).toContain('opa_properties_public')
})

test('a fact with no public page names our source and its as-of', async ({ page }) => {
  await registerAndSettle(page, 'lot-stored')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Land' }).click()

  const area = page.locator('[data-test="fact-lot-area"]')
  await area.locator('[data-test="show-me"]').click()

  const pop = area.locator('[data-test="show-me-stored"]')
  await expect(pop).toBeVisible()
  await expect(pop).toContainText('No public page for this')
})

test('the lot hands itself to the Analyst with the parcel already in context', async ({ page }) => {
  await registerAndSettle(page, 'lot-ask')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.locator('[data-test="parcel-action-ask"]').click()

  await expect(page).toHaveURL(/\/$|about=/)
  // The Analyst opens the conversation itself rather than making the buyer retype it.
  await expect(page.locator('[data-test="analyst-thread"]')).toBeVisible()
})

test('diligence is offered but plainly not available yet', async ({ page }) => {
  await registerAndSettle(page, 'lot-diligence')
  await openDossier(page, SEEDED.bestMargin.number)

  const button = page.locator('[data-test="parcel-action-diligence"]')
  await expect(button).toBeVisible()
  await expect(button).toBeDisabled()
  await expect(button).toContainText('$199')
})

test('editing an assumption moves the offer', async ({ page }) => {
  await registerAndSettle(page, 'lot-assumption')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.getByRole('tab', { name: 'Deal' }).click()
  await expect(page.locator('[data-test="deal-controls"]')).toBeVisible()

  const mao = page.locator('[data-test="deal-mao"]').first()
  await expect(mao).toBeVisible()

  // Two explicit margins rather than one. The market default is itself a margin, so
  // filling a single value can silently match it and assert nothing — which is exactly
  // how this passed locally and failed in CI.
  const margin = page.getByRole('spinbutton', { name: 'Target margin (%)' })
  const recompute = page.getByRole('button', { name: 'Recompute', exact: true })

  await margin.fill('35')
  await recompute.click()
  await expect.poll(async () => mao.innerText(), { timeout: 30000 }).not.toBe('')
  const permissive = await mao.innerText()

  await margin.fill('55')
  await recompute.click()
  await expect.poll(async () => mao.innerText(), { timeout: 30000 }).not.toBe(permissive)
})
