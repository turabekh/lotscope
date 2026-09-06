import { expect, test, type Page } from '@playwright/test'

import { registerAndSettle } from './support/app'

/** One SSE stream: two tool calls and a streamed answer, exactly as the runtime emits them. */
const STREAM = [
  'retry: 3000\n\n',
  'event: tool_started\ndata: {"tool":"live_li","input":{"parcel":"phl:191357500"}}\n\n',
  'event: tool_finished\ndata: {"tool":"live_li","data":{"live":{"open_violations":6},' +
    '"stored":{"open_violations":0},"diff":[{"field":"open_violations"}]},' +
    '"sources":[{"name":"violations (live)","url":"https://phl.carto.com/api/v2/sql?q=x",' +
    '"fetched_at":"2026-09-05T13:38:58Z","ingested_at":null,"computed_at":null},' +
    '{"name":"atlas","url":"https://atlas.phila.gov/191357500#violations","fetched_at":null,' +
    '"ingested_at":null,"computed_at":null}],"unverified":["L&I records what was reported."],' +
    '"duration_ms":812}\n\n',
  'event: text_delta\ndata: {"text":"L&I shows 6 open "}\n\n',
  'event: text_delta\ndata: {"text":"violations; our copy holds 0."}\n\n',
].join('')

async function mockAnalyst(page: Page): Promise<void> {
  await page.route('**/analyst/messages', (route) =>
    route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 99,
        conversation_id: 7,
        status: 'running',
        events_url: '/analyst/runs/99/events',
      }),
    }),
  )
  await page.route('**/analyst/runs/99/events', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: STREAM }),
  )
  await page.route('**/analyst/conversations', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  )
}

async function ask(page: Page): Promise<void> {
  await page.locator('[data-test="composer-input"]').fill('what is open on 3862 Aspen St')
  await page.locator('[data-test="composer-send"]').click()
  await expect(page.locator('[data-test="analyst-answer"]')).toContainText('L&I shows 6 open')
}

test('the Analyst streams an answer and shows what it checked', async ({ page }) => {
  await mockAnalyst(page)
  await registerAndSettle(page, 'analyst')
  await page.goto('/')

  await ask(page)

  const card = page.locator('[data-test="tool-card"]').first()
  await expect(card).toContainText('Checked L&I live')
  await expect(card).toContainText('1 differ')
})

test('a tool card expands to the envelope behind it', async ({ page }) => {
  await mockAnalyst(page)
  await registerAndSettle(page, 'analyst-expand')
  await page.goto('/')
  await ask(page)

  await expect(page.locator('[data-test="tool-card-body"]')).toHaveCount(0)
  await page.locator('[data-test="tool-card-toggle"]').first().click()

  const body = page.locator('[data-test="tool-card-body"]').first()
  await expect(body).toContainText('open_violations')
  await expect(body).toContainText('violations (live)')
  await expect(page.locator('[data-test="tool-unverified"]').first()).toContainText(
    'what was reported',
  )
})

test('an internal source opens the lot in the drawer', async ({ page }) => {
  await mockAnalyst(page)
  await registerAndSettle(page, 'analyst-drawer')
  await page.goto('/')
  await ask(page)

  await page.locator('[data-test="tool-card-toggle"]').first().click()
  await page.locator('[data-test="tool-source-internal"]').first().click()

  await expect(page.locator('[data-test="evidence-drawer"]')).toBeVisible()
  // The conversation is still there behind it: evidence opens beside the thread, not over it.
  await expect(page.locator('[data-test="analyst-answer"]')).toBeVisible()
})

test('the same flow works at 380px, by tap', async ({ page }) => {
  await page.setViewportSize({ width: 380, height: 820 })
  await mockAnalyst(page)
  await registerAndSettle(page, 'analyst-mobile')
  await page.goto('/')

  await ask(page)
  await page
    .locator('[data-test="tool-card-toggle"]')
    .first()
    .tap({ force: true })
    .catch(async () => {
      await page.locator('[data-test="tool-card-toggle"]').first().click()
    })
  await expect(page.locator('[data-test="tool-card-body"]').first()).toBeVisible()

  await page.locator('[data-test="tool-source-internal"]').first().click()
  const drawer = page.locator('[data-test="evidence-drawer"]')
  await expect(drawer).toBeVisible()

  // As a bottom sheet it must not push the page sideways.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)

  await page.locator('[data-test="evidence-close"]').click()
  await expect(drawer).toHaveCount(0)
})

test('evidence opens on the section the tool actually read', async ({ page }) => {
  await mockAnalyst(page)
  await registerAndSettle(page, 'analyst-anchor')
  await page.goto('/')
  await ask(page)

  await page.locator('[data-test="tool-card-toggle"]').first().click()
  await page.locator('[data-test="tool-source-internal"]').first().click()

  const drawer = page.locator('[data-test="evidence-drawer"]')
  await expect(drawer).toBeVisible()

  // live_li read the violations, so its lot link is anchored there and the drawer lands
  // on that section rather than at the top of the lot.
  const section = drawer.locator('#violations')
  await expect(section).toBeVisible()
  await expect
    .poll(async () =>
      section.evaluate((node) => {
        const box = node.getBoundingClientRect()
        return box.top < window.innerHeight && box.bottom > 0
      }),
    )
    .toBe(true)
})
