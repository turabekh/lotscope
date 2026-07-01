import type { LocationQuery } from 'vue-router'

import type { AreaShape } from '@/stores/areaSearch'

export type ExploreViewMode = 'list' | 'map' | 'split'

export const DEFAULT_VIEW_MODE: ExploreViewMode = 'split'

const VIEW_MODES: readonly ExploreViewMode[] = ['list', 'map', 'split']

export interface PaneVisibility {
  list: boolean
  map: boolean
}

export function paneVisibility(mode: ExploreViewMode): PaneVisibility {
  return {
    list: mode !== 'map',
    map: mode !== 'list',
  }
}

export function isExploreViewMode(value: unknown): value is ExploreViewMode {
  return typeof value === 'string' && VIEW_MODES.includes(value as ExploreViewMode)
}

export function readViewMode(value: unknown): ExploreViewMode {
  return isExploreViewMode(value) ? value : DEFAULT_VIEW_MODE
}

export interface MapBounds {
  north: number
  south: number
  east: number
  west: number
  zoom: number
}

export const VIEWPORT_MIN_ZOOM = 15

export function canListViewport(zoom: number): boolean {
  return zoom >= VIEWPORT_MIN_ZOOM
}

const AREA_SHAPES: readonly AreaShape[] = ['radius', 'polygon', 'neighborhood']
const DEFAULT_SHAPE: AreaShape = 'radius'

function isAreaShape(value: unknown): value is AreaShape {
  return typeof value === 'string' && AREA_SHAPES.includes(value as AreaShape)
}

function readMinScore(value: unknown): number | null {
  if (typeof value !== 'string') return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null
}

function readClasses(value: unknown): string[] {
  if (typeof value !== 'string' || value === '') return []
  return value.split(',').filter((item) => item.length > 0)
}

export interface ExploreState {
  view: ExploreViewMode
  shape: AreaShape
  vacantOnly: boolean
  useClasses: string[]
  minScore: number | null
}

export function readExploreState(query: LocationQuery): ExploreState {
  return {
    view: readViewMode(query.view),
    shape: isAreaShape(query.shape) ? query.shape : DEFAULT_SHAPE,
    vacantOnly: query.vacant === '1',
    useClasses: readClasses(query.classes),
    minScore: readMinScore(query.minScore),
  }
}

export function exploreQuery(state: ExploreState): Record<string, string> {
  const query: Record<string, string> = {}
  if (state.view !== DEFAULT_VIEW_MODE) query.view = state.view
  if (state.shape !== DEFAULT_SHAPE) query.shape = state.shape
  if (state.vacantOnly) query.vacant = '1'
  if (state.useClasses.length > 0) query.classes = state.useClasses.join(',')
  if (state.minScore !== null) query.minScore = String(state.minScore)
  return query
}

export function boundsToPolygon(bounds: MapBounds): GeoJSON.Polygon {
  const { north, south, east, west } = bounds
  return {
    type: 'Polygon',
    coordinates: [
      [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ],
    ],
  }
}
