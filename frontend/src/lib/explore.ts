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
