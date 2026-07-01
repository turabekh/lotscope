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
