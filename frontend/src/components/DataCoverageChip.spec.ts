import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DataCoverageChip from '@/components/DataCoverageChip.vue'

describe('DataCoverageChip', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  function mountChip() {
    return mount(DataCoverageChip, { global: { plugins: [[Quasar, {}]] } })
  }

  it('names Philadelphia and its flagship coverage', () => {
    const text = mountChip().text()
    expect(text).toContain('Philadelphia')
    expect(text).toContain('flagship')
  })
})
