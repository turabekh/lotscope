import { describe, expect, it } from 'vitest'

import { screeningDisplay } from '@/lib/screening'
import type { Recommendation } from '@/lib/types'

const ALL: Recommendation[] = [
  'strong_candidate',
  'worth_investigating',
  'high_entitlement_risk',
  'economics_unattractive',
  'insufficient_data',
  'likely_pass',
]

describe('screening display', () => {
  it('renders every recommendation the contract can produce', () => {
    for (const value of ALL) {
      expect(screeningDisplay(value)?.label).toBeTruthy()
    }
  })

  it('shows nothing when the verdict predates the decision contract', () => {
    expect(screeningDisplay(null)).toBeNull()
  })

  it('does not present insufficient data as a positive result', () => {
    expect(screeningDisplay('insufficient_data')?.tone).not.toBe('positive')
    expect(screeningDisplay('likely_pass')?.tone).not.toBe('positive')
  })

  it('reserves the positive tone for the single strongest label', () => {
    const positives = ALL.filter((value) => screeningDisplay(value)?.tone === 'positive')
    expect(positives).toEqual(['strong_candidate'])
  })
})
