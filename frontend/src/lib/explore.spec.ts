import { describe, expect, it } from 'vitest'

import { isExploreViewMode, paneVisibility, readViewMode } from '@/lib/explore'

describe('paneVisibility', () => {
  it('split shows both panes', () => {
    expect(paneVisibility('split')).toEqual({ list: true, map: true })
  })

  it('map shows only the map', () => {
    expect(paneVisibility('map')).toEqual({ list: false, map: true })
  })

  it('list shows only the list', () => {
    expect(paneVisibility('list')).toEqual({ list: true, map: false })
  })
})

describe('readViewMode', () => {
  it('accepts valid modes', () => {
    expect(readViewMode('list')).toBe('list')
    expect(readViewMode('map')).toBe('map')
    expect(readViewMode('split')).toBe('split')
  })

  it('falls back to split for missing or invalid values', () => {
    expect(readViewMode(undefined)).toBe('split')
    expect(readViewMode('nope')).toBe('split')
    expect(readViewMode(['list'])).toBe('split')
  })
})

describe('isExploreViewMode', () => {
  it('narrows valid mode strings only', () => {
    expect(isExploreViewMode('map')).toBe(true)
    expect(isExploreViewMode('x')).toBe(false)
    expect(isExploreViewMode(null)).toBe(false)
  })
})
