export type LaunchPresentation = 'flagship' | 'pilot' | 'unavailable'

export interface LaunchStatusDisplay {
  presentation: LaunchPresentation
  badge: string | null
  tone: string
  summary: string
}

const FLAGSHIP: LaunchStatusDisplay = {
  presentation: 'flagship',
  badge: 'flagship',
  tone: 'primary',
  summary:
    'The flagship market: the full data stack is loaded and every product surface is available. Outputs remain preliminary screening, not a professional determination.',
}

const PILOT: LaunchStatusDisplay = {
  presentation: 'pilot',
  badge: 'pilot',
  tone: 'amber-8',
  summary:
    'A pilot market. Coverage is narrower than the flagship and some sources are unavailable, so results here are less complete. Check the source freshness panel before relying on a result.',
}

const UNAVAILABLE: LaunchStatusDisplay = {
  presentation: 'unavailable',
  badge: 'unavailable',
  tone: 'grey-6',
  summary: 'This market is not available. No coverage claim is made for it.',
}

export function launchStatusDisplay(launchStatus: string | undefined): LaunchStatusDisplay {
  if (launchStatus === 'live') return FLAGSHIP
  if (launchStatus === 'pilot') return PILOT
  return UNAVAILABLE
}

export function isFlagship(launchStatus: string | undefined): boolean {
  return launchStatusDisplay(launchStatus).presentation === 'flagship'
}

export function isPilot(launchStatus: string | undefined): boolean {
  return launchStatusDisplay(launchStatus).presentation === 'pilot'
}
