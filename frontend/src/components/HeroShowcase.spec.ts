import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HeroShowcase from '@/components/HeroShowcase.vue'

function mountShowcase() {
  return mount(HeroShowcase, { global: { plugins: [[Quasar, {}]] } })
}

describe('HeroShowcase', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('opens on the verdict and keeps the parcel identity fixed', () => {
    const wrapper = mountShowcase()
    expect(wrapper.text()).toContain('1500 S Broad St')
    expect(wrapper.text()).toContain('Example')
    expect(wrapper.find('[data-test="showcase-tab-verdict"]').attributes('aria-selected')).toBe(
      'true',
    )
  })

  it('advances to the next view on its own', async () => {
    const wrapper = mountShowcase()
    vi.advanceTimersByTime(4300)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="showcase-tab-deal"]').attributes('aria-selected')).toBe('true')
  })

  it('wraps around rather than stopping at the last view', async () => {
    const wrapper = mountShowcase()
    vi.advanceTimersByTime(4300 * 6)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="showcase-tab-verdict"]').attributes('aria-selected')).toBe(
      'true',
    )
  })

  it('lets a visitor jump straight to a view', async () => {
    const wrapper = mountShowcase()
    await wrapper.find('[data-test="showcase-tab-risk"]').trigger('click')
    expect(wrapper.find('[data-test="showcase-tab-risk"]').attributes('aria-selected')).toBe('true')
  })

  it('renders every example so none is only reachable by waiting', () => {
    const wrapper = mountShowcase()
    const text = wrapper.text()
    expect(text).toContain('Base district · 3 units')
    expect(text).toContain('Max allowable offer $165,708')
    expect(text).toContain('Risk 20 / 100')
    expect(text).toContain('3 recorded sales nearby')
    expect(text).toContain('Title 14 §14-701 · §14-702')
  })

  it('stops the timer when it is removed', () => {
    const clear = vi.spyOn(globalThis, 'clearInterval')
    mountShowcase().unmount()
    expect(clear).toHaveBeenCalled()
  })
})
