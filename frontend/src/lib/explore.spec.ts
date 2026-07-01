import { describe, expect, it } from 'vitest'

import { paneVisibility } from '@/lib/explore'

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
