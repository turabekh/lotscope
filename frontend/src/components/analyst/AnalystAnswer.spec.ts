import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AnalystAnswer from '@/components/analyst/AnalystAnswer.vue'

describe('AnalystAnswer', () => {
  it('renders a table as a table', () => {
    const wrapper = mount(AnalystAnswer, {
      props: {
        text: '| Parcel | Comp low |\n|---|---|\n| phl:463278700 | $50,000 |',
      },
    })
    expect(wrapper.find('[data-test="analyst-table"]').exists()).toBe(true)
    expect(wrapper.findAll('th').map((th) => th.text())).toEqual(['Parcel', 'Comp low'])
    expect(wrapper.find('td').text()).toBe('phl:463278700')
    expect(wrapper.text()).not.toContain('|---|')
  })

  it('renders bold without leaving the asterisks in', () => {
    const wrapper = mount(AnalystAnswer, { props: { text: 'Screened **2026-09-16** today' } })
    expect(wrapper.find('strong').text()).toBe('2026-09-16')
    expect(wrapper.text()).not.toContain('**')
  })

  it('shows model output as text and never as markup', () => {
    const wrapper = mount(AnalystAnswer, { props: { text: '<img src=x onerror=alert(1)>' } })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })
})
