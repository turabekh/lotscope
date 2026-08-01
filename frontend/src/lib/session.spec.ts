import { describe, expect, it } from 'vitest'

import {
  isTokenExpired,
  millisecondsUntilRefresh,
  shouldRefreshToken,
  tokenExpiresAt,
} from '@/lib/session'

function tokenExpiringAt(epochSeconds: number): string {
  const payload = btoa(JSON.stringify({ sub: '1', exp: epochSeconds }))
  return `header.${payload}.signature`
}

const NOW = 1_785_000_000_000

describe('tokenExpiresAt', () => {
  it('reads the expiry out of the token', () => {
    expect(tokenExpiresAt(tokenExpiringAt(NOW / 1000 + 60))).toBe((NOW / 1000 + 60) * 1000)
  })

  it('returns nothing for a token it cannot read', () => {
    expect(tokenExpiresAt('not-a-jwt')).toBeNull()
    expect(tokenExpiresAt('a.b.c')).toBeNull()
    expect(tokenExpiresAt(null)).toBeNull()
  })
})

describe('isTokenExpired', () => {
  it('treats a missing token as expired', () => {
    expect(isTokenExpired(null, NOW)).toBe(true)
  })

  it('treats a past expiry as expired', () => {
    expect(isTokenExpired(tokenExpiringAt(NOW / 1000 - 1), NOW)).toBe(true)
  })

  it('expires slightly early so a request in flight does not land dead', () => {
    expect(isTokenExpired(tokenExpiringAt(NOW / 1000 + 5), NOW)).toBe(true)
    expect(isTokenExpired(tokenExpiringAt(NOW / 1000 + 120), NOW)).toBe(false)
  })

  it('does not sign out a user over a token it cannot parse', () => {
    expect(isTokenExpired('opaque-token', NOW)).toBe(false)
  })
})

describe('shouldRefreshToken', () => {
  it('refreshes inside the lead window', () => {
    expect(shouldRefreshToken(tokenExpiringAt(NOW / 1000 + 5 * 60), NOW)).toBe(true)
  })

  it('leaves a fresh token alone', () => {
    expect(shouldRefreshToken(tokenExpiringAt(NOW / 1000 + 60 * 60), NOW)).toBe(false)
  })

  it('does not try to refresh a token that is already dead', () => {
    expect(shouldRefreshToken(tokenExpiringAt(NOW / 1000 - 60), NOW)).toBe(false)
  })
})

describe('millisecondsUntilRefresh', () => {
  it('counts down to the lead window', () => {
    expect(millisecondsUntilRefresh(tokenExpiringAt(NOW / 1000 + 30 * 60), NOW)).toBe(
      20 * 60 * 1000,
    )
  })

  it('never returns a negative delay', () => {
    expect(millisecondsUntilRefresh(tokenExpiringAt(NOW / 1000 + 60), NOW)).toBe(0)
  })
})
