import { expect, test } from '@playwright/test'

import { openDossier, registerAndSettle, SEEDED } from './support/app'

test('a lot shows where a fact came from', async ({ page }) => {
  await registerAndSettle(page, 'lot-showme')
  await openDossier(page, SEEDED.bestMargin.number)

  // The zoning section carries the property facts now; no tab to click.
  await page.locator('[data-test="lot-nav-zoning-overlays"]').click()

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

  await page.locator('[data-test="lot-nav-zoning-overlays"]').click()

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

test('editing an assumption is applied to the deal', async ({ page }) => {
  await registerAndSettle(page, 'lot-assumption')
  await openDossier(page, SEEDED.bestMargin.number)

  // The deal sits in the verdict section now.
  await expect(page.locator('[data-test="deal-controls"]')).toBeVisible()

  await page.getByRole('spinbutton', { name: 'Target margin (%)' }).fill('35')
  await page.getByRole('button', { name: 'Recompute', exact: true }).click()

  // That the offer moves with the margin is arithmetic, and it is asserted in
  // deal/tests/test_analysis.py where it holds for every fixture. What the browser can
  // prove is that the control reaches the deal at all: the seeded lot is infeasible, so
  // its price reads the same either way and asserting on it would prove nothing.
  // Reset becoming available is the signal that an override is in force. The
  // "Assumptions:" line reports where the cost figures came from, not whether the buyer
  // changed anything, so it correctly stays as it was.
  await expect(page.getByRole('button', { name: 'Reset', exact: true })).toBeEnabled()
})

test('a lot opened at a section starts there', async ({ page }) => {
  await registerAndSettle(page, 'lot-anchor')
  await page.goto(`/lot/${SEEDED.bestMargin.number}#violations`)

  const section = page.locator('#violations')
  await expect(section).toBeVisible()

  // "In view" means in the viewport, not merely present in the document.
  const inView = await section.evaluate((node) => {
    const box = node.getBoundingClientRect()
    return box.top < window.innerHeight && box.bottom > 0
  })
  expect(inView).toBe(true)
})

test('every section is on one page, no tab to click', async ({ page }) => {
  await registerAndSettle(page, 'lot-flat')
  await openDossier(page, SEEDED.bestMargin.number)

  for (const id of ['verdict', 'deeds', 'violations', 'delinquency', 'comps', 'neighbors']) {
    await expect(page.locator(`#${id}`)).toHaveCount(1)
  }
  await expect(page.locator('[data-test="lot-section-nav"]')).toBeVisible()
})

test('the section nav moves the page', async ({ page }) => {
  await registerAndSettle(page, 'lot-nav')
  await openDossier(page, SEEDED.bestMargin.number)

  await page.locator('[data-test="lot-nav-comps"]').click()
  await expect
    .poll(async () =>
      page.locator('#comps').evaluate((node) => node.getBoundingClientRect().top < 400),
    )
    .toBe(true)
})

test('the record sections show the records, with where each came from', async ({ page }) => {
  await registerAndSettle(page, 'lot-evidence')
  await openDossier(page, SEEDED.delinquent.number)

  // Deeds: the transfer, its parties, and a way to open it.
  const deeds = page.locator('[data-test="deeds-table"]')
  await expect(deeds).toBeVisible()
  await expect(deeds).toContainText('PRIOR OWNER LLC')

  // Violations: open versus on record is the distinction, not a bare count.
  await expect(page.locator('[data-test="violations-lede"]')).toContainText(
    '2 violations on record, 1 is open',
  )
  await expect(page.locator('[data-test="violation-unsafe"]')).toBeVisible()

  // Delinquency: the debt names the owner before last, and the page says so.
  await expect(page.locator('[data-test="delinquency-debtor"]')).toHaveText('PRIOR OWNER LLC')
  await expect(page.locator('[data-test="delinquency-attribution"]')).toContainText(
    'not the current owner',
  )

  // Sheriff: postponed, but the date is still ahead, so it is scheduled.
  await expect(page.locator('[data-test="sheriff-table"]')).toContainText('E2E-2301-0001')
  await expect(page.locator('[data-test="sheriff-scheduled"]').first()).toBeVisible()

  // Every section carries its provenance foot.
  await expect(page.locator('[data-test="evidence-sources"]').first()).toBeVisible()
})

test('a lot with no listing says so rather than hiding the section', async ({ page }) => {
  await registerAndSettle(page, 'lot-no-listing')
  await openDossier(page, SEEDED.bestMargin.number)

  await expect(page.locator('[data-test="sheriff-empty"]')).toBeVisible()
  await expect(page.locator('[data-test="lot-nav-sheriff"]')).toBeVisible()
})

test('the section nav holds its own height and the page does not scroll through it', async ({
  page,
}) => {
  await registerAndSettle(page, 'lot-nav-band')
  await openDossier(page, SEEDED.delinquent.number)
  await page.locator('[data-test="lot-nav-comps"]').click()

  const geometry = await page.evaluate(() => {
    const nav = document.querySelector('[data-test="lot-section-nav"]') as HTMLElement
    const pane = nav.parentElement as HTMLElement
    const comps = document.getElementById('comps')!.getBoundingClientRect()
    return {
      height: nav.getBoundingClientRect().height,
      gapAboveNav: nav.getBoundingClientRect().top - pane.getBoundingClientRect().top,
      compsUnderNav: comps.top - nav.getBoundingClientRect().bottom,
    }
  })

  // A flex child with its own overflow collapses to nothing unless it refuses to shrink.
  expect(geometry.height).toBeGreaterThanOrEqual(34)
  // Sticky at the scrollport, so no strip of page slides past above it.
  expect(geometry.gapAboveNav).toBeLessThanOrEqual(1)
  // And a section it jumps to lands below it, not under it.
  expect(geometry.compsUnderNav).toBeGreaterThanOrEqual(0)
})
