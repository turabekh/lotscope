import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import AnalystComposer from '@/components/analyst/AnalystComposer.vue'

function composer(props: Record<string, unknown> = {}) {
  return mount(AnalystComposer, {
    props: { busy: false, ...props },
    global: { plugins: [[Quasar, {}]] },
  })
}

describe('AnalystComposer', () => {
  it('sends what was typed', async () => {
    const wrapper = composer()
    await wrapper.find('[data-test="composer-input"]').setValue('who owns 3862 Aspen St')
    await wrapper.find('[data-test="composer-send"]').trigger('click')

    expect(wrapper.emitted('send')?.[0]).toEqual(['who owns 3862 Aspen St'])
  })

  it('will not send an empty message', async () => {
    const wrapper = composer()
    await wrapper.find('[data-test="composer-input"]').setValue('   ')
    expect(wrapper.find('[data-test="composer-send"]').attributes('disabled')).toBeDefined()
  })

  it('clears the box after sending so the next question starts empty', async () => {
    const wrapper = composer()
    const input = wrapper.find('[data-test="composer-input"]')
    await input.setValue('screen the sale')
    await wrapper.find('[data-test="composer-send"]').trigger('click')

    expect((input.element as HTMLTextAreaElement).value).toBe('')
  })

  it('shortcuts insert text and send nothing on their own', async () => {
    const wrapper = composer()
    const shortcuts = wrapper.findAll('[data-test="composer-shortcut"]')
    expect(shortcuts).toHaveLength(2)

    await shortcuts[0].trigger('click')

    const input = wrapper.find('[data-test="composer-input"]')
    expect((input.element as HTMLTextAreaElement).value).toBe('Screen the next sale')
    // The buyer still presses send: a shortcut is a faster way to type, not a second way
    // to ask, so what runs is always what they can see.
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('offers stop instead of send while the Analyst is working', async () => {
    const wrapper = composer({ busy: true })
    expect(wrapper.find('[data-test="composer-send"]').exists()).toBe(false)
    await wrapper.find('[data-test="composer-stop"]').trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('takes the server suggested opening prompt', () => {
    const wrapper = composer({ suggestion: 'Screen the 2026-09-16 sale against my buy box' })
    const input = wrapper.find('[data-test="composer-input"]')
    expect((input.element as HTMLTextAreaElement).value).toContain('2026-09-16')
  })

  it('spells out which sale is next when the server knows the date', async () => {
    const wrapper = composer({ suggestion: 'Screen the 2026-09-16 sale against my buy box' })
    await wrapper.findAll('[data-test="composer-shortcut"]')[0].trigger('click')

    const input = wrapper.find('[data-test="composer-input"]')
    expect((input.element as HTMLTextAreaElement).value).toContain('2026-09-16')
  })

  it('keeps every control tappable', () => {
    const wrapper = composer()
    const html = wrapper.html()
    expect(html).toContain('data-test="composer-shortcut"')
    expect(html).toContain('data-test="composer-send"')
  })
})
