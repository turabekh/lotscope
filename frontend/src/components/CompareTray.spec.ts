import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import CompareTray from '@/components/CompareTray.vue'
import { useCompareStore } from '@/stores/compare'

function mountTray() {
  return mount(CompareTray, { global: { plugins: [[Quasar, {}]] } })
}

describe('CompareTray', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders nothing when the compare store is empty', () => {
    const wrapper = mountTray()
    expect(wrapper.find('.compare-tray').exists()).toBe(false)
  })

  it('shows the count and a chip per selected parcel', async () => {
    const compare = useCompareStore()
    compare.add('001')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.compare-tray').exists()).toBe(true)
    expect(wrapper.find('.tray-count').text()).toBe('1 of 4 selected')
    expect(wrapper.findAllComponents({ name: 'QChip' })).toHaveLength(1)
  })

  it('says what is needed while comparing is not yet possible', async () => {
    const compare = useCompareStore()
    compare.add('phl:001')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.tray-hint').text()).toContain('Add one more lot')
  })

  it('says it is ready once two lots are selected', async () => {
    const compare = useCompareStore()
    compare.add('phl:001')
    compare.add('phl:002')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.tray-hint').text()).toContain('Ready')
  })

  it('names a lot by its address when one was recorded', async () => {
    const compare = useCompareStore()
    compare.add('phl:001', '616 E INDIANA AVE')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('616 E INDIANA AVE')
  })

  it('falls back to the local key rather than showing a prefixed id', async () => {
    const compare = useCompareStore()
    compare.add('phl:331001000')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('331001000')
    expect(wrapper.text()).not.toContain('phl:331001000')
  })

  it('disables Compare below two selections and enables it at two', async () => {
    const compare = useCompareStore()
    compare.add('001')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    const button = () => wrapper.findAll('button').find((b) => b.text().includes('Compare'))
    expect(button()?.attributes('disabled')).toBeDefined()

    compare.add('002')
    await wrapper.vm.$nextTick()
    expect(button()?.attributes('disabled')).toBeUndefined()
  })

  it('clears the selection when Clear is pressed', async () => {
    const compare = useCompareStore()
    compare.add('001')
    compare.add('002')
    const wrapper = mountTray()
    await wrapper.vm.$nextTick()
    const clear = wrapper.findAll('button').find((b) => b.text().includes('Clear'))
    await clear?.trigger('click')
    expect(compare.count).toBe(0)
    expect(wrapper.find('.compare-tray').exists()).toBe(false)
  })
})
