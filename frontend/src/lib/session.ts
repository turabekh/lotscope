const EXPIRY_SKEW_SECONDS = 30
const REFRESH_LEAD_SECONDS = 10 * 60

interface JwtPayload {
  exp?: number
}

function decodePayload(token: string): JwtPayload | null {
  const segments = token.split('.')
  if (segments.length !== 3) return null
  const segment = segments[1]
  if (segment === undefined) return null
  try {
    const normalised = segment.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalised.padEnd(Math.ceil(normalised.length / 4) * 4, '=')
    return JSON.parse(atob(padded)) as JwtPayload
  } catch {
    return null
  }
}

export function tokenExpiresAt(token: string | null): number | null {
  if (token === null) return null
  const payload = decodePayload(token)
  if (payload === null || typeof payload.exp !== 'number') return null
  return payload.exp * 1000
}

export function isTokenExpired(token: string | null, now = Date.now()): boolean {
  if (token === null) return true
  const expiresAt = tokenExpiresAt(token)
  if (expiresAt === null) return false
  return expiresAt - EXPIRY_SKEW_SECONDS * 1000 <= now
}

export function shouldRefreshToken(token: string | null, now = Date.now()): boolean {
  if (token === null) return false
  if (isTokenExpired(token, now)) return false
  const expiresAt = tokenExpiresAt(token)
  if (expiresAt === null) return false
  return expiresAt - REFRESH_LEAD_SECONDS * 1000 <= now
}

export function millisecondsUntilRefresh(token: string | null, now = Date.now()): number | null {
  const expiresAt = tokenExpiresAt(token)
  if (expiresAt === null) return null
  return Math.max(0, expiresAt - REFRESH_LEAD_SECONDS * 1000 - now)
}
