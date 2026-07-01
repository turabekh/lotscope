import { describe, expect, it } from 'vitest'

import {
  boundsToPolygon,
  canListViewport,
  exploreQuery,
  type ExploreState,
  isExploreViewMode,
  type MapBounds,
  paneVisibility,
  readExploreState,
  readViewMode,
} from '@/lib/explore'

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

describe('canListViewport', () => {
  it('gates viewport listing below the zoom threshold', () => {
    expect(canListViewport(15)).toBe(true)
    expect(canListViewport(17.5)).toBe(true)
    expect(canListViewport(14.9)).toBe(false)
    expect(canListViewport(13)).toBe(false)
  })
})

describe('explore query codec', () => {
  it('round-trips a non-default state', () => {
    const state: ExploreState = {
      view: 'map',
      shape: 'polygon',
      vacantOnly: true,
      useClasses: ['R', 'C'],
      minScore: 70,
    }
    expect(readExploreState(exploreQuery(state))).toEqual(state)
  })

  it('omits defaults from the query string', () => {
    expect(
      exploreQuery({
        view: 'split',
        shape: 'radius',
        vacantOnly: false,
        useClasses: [],
        minScore: null,
      }),
    ).toEqual({})
  })

  it('falls back to defaults for invalid query values', () => {
    expect(readExploreState({ view: 'x', shape: 'blob', vacant: 'yes', minScore: '999' })).toEqual({
      view: 'split',
      shape: 'radius',
      vacantOnly: false,
      useClasses: [],
      minScore: null,
    })
  })
})

describe('boundsToPolygon', () => {
  it('builds a closed rectangle ring from map bounds', () => {
    const bounds: MapBounds = { north: 40, south: 39, east: -75, west: -76, zoom: 16 }
    const polygon = boundsToPolygon(bounds)
    expect(polygon.type).toBe('Polygon')
    const ring = polygon.coordinates[0]
    expect(ring).toHaveLength(5)
    expect(ring[0]).toEqual([-76, 39])
    expect(ring[2]).toEqual([-75, 40])
    expect(ring[0]).toEqual(ring[4])
  })
})
