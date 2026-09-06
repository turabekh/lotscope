import { chromium } from '@playwright/test'

const BASE = 'https://parcelphl.online'
const EMAIL = process.env.EMAIL
const PASSWORD = 'Sup3rSecret!walk'
const SHOTS = process.env.SHOTS
const errors = []

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('input[type="email"], input[aria-label*="mail" i]').first().fill(EMAIL)
  await page.locator('input[type="password"]').first().fill(PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).first().click()
  await page.waitForTimeout(4000)
  console.log('AFTER_LOGIN_URL=' + page.url())

  await page.goto(`${BASE}/analyst`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${SHOTS}/budget-1-analyst.png` })

  const box = page.locator('textarea, [contenteditable="true"]').first()
  for (let turn = 1; turn <= 4; turn++) {
    await box.click()
    await box.fill(`Turn ${turn}: what is at 902 S Cecil St?`)
    await page.keyboard.press('Enter')
    // Long enough for a real run with live reads to finish or be refused.
    for (let i = 0; i < 40; i++) {
      await sleep(3000)
      const text = await page.locator('body').innerText()
      if (/daily Analyst budget/i.test(text)) {
        console.log(`REFUSED_ON_TURN=${turn}`)
        const line = text.split('\n').find((l) => /daily Analyst budget/i.test(l))
        console.log('THREAD_MESSAGE=' + (line ?? '').trim())
        await page.screenshot({ path: `${SHOTS}/budget-2-refused.png`, fullPage: true })
        await finish(browser, page)
        return
      }
      const busy = await page.locator('.q-spinner, [data-test="analyst-running"]').count()
      if (busy === 0 && i > 3) break
    }
    console.log(`TURN_${turn}_DONE`)
  }
  console.log('NEVER_REFUSED')
  await page.screenshot({ path: `${SHOTS}/budget-2-refused.png`, fullPage: true })
  await finish(browser, page)
}

async function finish(browser, page) {
  const token = await page.evaluate(() => localStorage.getItem('lotscope_token'))
  console.log('TOKEN=' + token)
  await browser.close()
}

main().then(() => { console.log('PAGE_ERRORS=' + errors.length); errors.forEach((e) => console.log('  ' + e)) })
