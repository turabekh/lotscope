import { describe, expect, it } from 'vitest'

import { isFlagship, isPilot, launchStatusDisplay } from '@/lib/market-status'

describe('launch status presentation', () => {
  it('presents a live market as the flagship', () => {
    const display = launchStatusDisplay('live')
    expect(display.presentation).toBe('flagship')
    expect(display.badge).toBe('flagship')
  })

  it('presents a pilot market as a pilot', () => {
    expect(launchStatusDisplay('pilot').presentation).toBe('pilot')
    expect(isPilot('pilot')).toBe(true)
    expect(isFlagship('pilot')).toBe(false)
  })

  it('treats an unknown or missing status as unavailable rather than flagship', () => {
    for (const status of [undefined, '', 'graduating', 'coming_soon']) {
      expect(launchStatusDisplay(status).presentation).toBe('unavailable')
      expect(isFlagship(status)).toBe(false)
    }
  })

  it('never claims a market is verified, because the gold-set gate is not met', () => {
    for (const status of ['live', 'pilot', 'unknown']) {
      const display = launchStatusDisplay(status)
      const text = `${display.badge ?? ''} ${display.summary}`.toLowerCase()
      expect(text).not.toContain('verified')
      expect(text).not.toContain('guaranteed')
      expect(text).not.toContain('approved')
    }
  })

  it('tells a pilot user their coverage is narrower before they rely on a result', () => {
    const summary = launchStatusDisplay('pilot').summary.toLowerCase()
    expect(summary).toContain('narrower')
    expect(summary).toContain('unavailable')
  })

  it('keeps the flagship summary preliminary rather than conclusive', () => {
    expect(launchStatusDisplay('live').summary.toLowerCase()).toContain('preliminary')
  })
})
