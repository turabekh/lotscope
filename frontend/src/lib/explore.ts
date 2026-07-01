export type ExploreViewMode = 'list' | 'map' | 'split'

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
