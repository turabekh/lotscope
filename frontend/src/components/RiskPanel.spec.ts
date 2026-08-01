import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import RiskPanel from '@/components/RiskPanel.vue'
import type { RiskFlag, VerdictResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function flag(code: string, severity: string, label: string): RiskFlag {
  return { code, severity, label, detail: `${label} detail`, source: 'li' } as RiskFlag
}

function mountPanel(verdict: Partial<VerdictResult> | null) {
  const store = useParcelStore()
  store.verdict = verdict === null ? null : ({ risk_flags: [], ...verdict } as VerdictResult)
  return mount(RiskPanel, { global: { plugins: [[Quasar, {}]] } })
}

describe('RiskPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('says a clean lot was checked rather than showing nothing', () => {
    const wrapper = mountPanel({ risk_score: 0, risk_flags: [] })
    expect(wrapper.find('[data-test="risk-panel-clear"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('No risk flags recorded')
    expect(wrapper.text()).toContain('not a guarantee')
  })

  it('renders every flag grouped by severity', () => {
    const wrapper = mountPanel({
      risk_score: 45,
      risk_flags: [
        flag('a', 'low', 'RCO notification'),
        flag('b', 'high', 'Tax lien'),
        flag('c', 'medium', 'Open L&I violation'),
      ],
    })
    expect(wrapper.findAll('[data-test="risk-panel-flag"]')).toHaveLength(3)
    const text = wrapper.text()
    expect(text.indexOf('Deal killers')).toBeLessThan(text.indexOf('Needs attention'))
    expect(text.indexOf('Needs attention')).toBeLessThan(text.indexOf('Worth knowing'))
  })

  it('warns when a deal killer is present', () => {
    const wrapper = mountPanel({ risk_score: 70, risk_flags: [flag('b', 'high', 'Tax lien')] })
    expect(wrapper.text()).toContain('can kill a deal')
  })

  it('does not call a below-threshold score an all-clear when flags exist', () => {
    const wrapper = mountPanel({
      risk_score: 30,
      risk_flags: [flag('a', 'low', 'RCO'), flag('c', 'medium', 'L&I')],
    })
    expect(wrapper.text()).toContain('2 flags recorded')
    expect(wrapper.text()).toContain('review them before committing')
    expect(wrapper.find('[data-test="risk-panel-clear"]').exists()).toBe(false)
  })

  it('explains an absent verdict instead of rendering an empty card', () => {
    const wrapper = mountPanel(null)
    expect(wrapper.find('[data-test="risk-panel-no-verdict"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('No verdict computed yet')
  })
})
