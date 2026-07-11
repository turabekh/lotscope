import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { UPGRADE_COPY } from '@/lib/upgrade'

const stubs = {
  QBtn: { props: ['label'], template: '<button @click="$emit(\'click\')">{{ label }}</button>' },
  QIcon: { template: '<i />' },
}

describe('UpgradePrompt', () => {
  it('renders the centralized copy for the given cap', () => {
    const wrapper = mount(UpgradePrompt, {
      props: { cap: 'saved_search' },
      global: { plugins: [[Quasar, {}]], stubs },
    })
    expect(wrapper.text()).toContain(UPGRADE_COPY.saved_search.headline)
    expect(wrapper.text()).toContain(UPGRADE_COPY.saved_search.detail)
    expect(wrapper.text()).toContain('See plans')
  })

  it('emits dismiss when dismissible and closed', async () => {
    const wrapper = mount(UpgradePrompt, {
      props: { cap: 'ask', dismissible: true, cta: 'Upgrade' },
      global: { plugins: [[Quasar, {}]], stubs },
    })
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    expect(wrapper.emitted('dismiss')).toBeTruthy()
  })
})
