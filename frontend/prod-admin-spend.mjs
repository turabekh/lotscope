import { chromium } from '@playwright/test'
const BASE = 'https://parcelphl.online'
const SHOTS = process.env.SHOTS
const TOKEN = process.env.ADMIN_TOKEN
const errors = []
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`) })
await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await page.evaluate((t) => localStorage.setItem('lotscope_token', t), TOKEN)
await page.goto(`${BASE}/admin`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(6000)
const total = await page.locator('[data-test="spend-total"]').innerText().catch(() => 'MISSING')
const pct = await page.locator('[data-test="spend-pct"]').innerText().catch(() => 'MISSING')
const rows = await page.locator('[data-test="spend-row"]').allInnerTexts().catch(() => [])
console.log('SPEND_TOTAL=' + total)
console.log('SPEND_PCT=' + pct)
rows.forEach((r) => console.log('SPEND_ROW=' + r.replace(/\s+/g, ' ').trim()))
await page.locator('[data-test="spend-total"]').scrollIntoViewIfNeeded().catch(() => {})
await page.screenshot({ path: `${SHOTS}/budget-3-admin-spend.png` })
await browser.close()
console.log('PAGE_ERRORS=' + errors.length)
errors.forEach((e) => console.log('  ' + e))
