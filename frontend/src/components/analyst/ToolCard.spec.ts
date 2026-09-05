import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import ToolCard from '@/components/analyst/ToolCard.vue'
import { internalParcel, toolSummary } from '@/components/analyst/toolSummary'
import type { ToolCall } from '@/stores/analyst'

function call(overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    name: 'live_li',
    input: { parcel: 'phl:191357500' },
    envelope: {
      data: {
        live: { open_violations: 6 },
        stored: { open_violations: 0 },
        diff: [{ field: 'x' }],
      },
      sources: [
        {
          name: 'violations (live)',
          url: 'https://phl.carto.com/api/v2/sql?q=SELECT',
          fetched_at: '2026-09-05T13:38:58Z',
          ingested_at: null,
          computed_at: null,
        },
        {
          name: 'atlas',
          url: 'https://atlas.phila.gov/191357500',
          fetched_at: null,
          ingested_at: null,
          computed_at: null,
        },
      ],
      unverified: ['L&I records what was reported.'],
    },
    durationMs: 812,
    running: false,
    ...overrides,
  }
}

function card(overrides: Partial<ToolCall> = {}) {
  return mount(ToolCard, {
    props: { call: call(overrides) },
    global: { plugins: [[Quasar, {}]] },
  })
}

describe('toolSummary', () => {
  it('says what was checked and what it found', () => {
    expect(toolSummary(call())).toBe('Checked L&I live · 1 differ')
  })

  it('says so when the live read agrees', () => {
    expect(
      toolSummary(call({ envelope: { data: { diff: [] }, sources: [], unverified: [] } })),
    ).toBe('Checked L&I live · agrees with our copy')
  })

  it('counts a screen in lots and BIDs', () => {
    const screen = call({
      name: 'screen_sale',
      envelope: { data: { screened: 32, bid: 3 }, sources: [], unverified: [] },
    })
    expect(toolSummary(screen)).toBe('Screened the sale · 32 lots · 3 BID')
  })

  it('shows a running call without inventing a result', () => {
    expect(toolSummary(call({ running: true, envelope: null }))).toBe('Checked L&I live…')
  })

  it('falls back to the tool name rather than a blank', () => {
    expect(toolSummary(call({ name: 'some_new_tool', envelope: null, running: false }))).toBe(
      'some new tool',
    )
  })
})

describe('internalParcel', () => {
  it('recognises a lot we can open ourselves', () => {
    expect(internalParcel('https://atlas.phila.gov/191357500')).toBe('phl:191357500')
  })

  it('leaves an external source external', () => {
    expect(internalParcel('https://phl.carto.com/api/v2/sql?q=SELECT')).toBeNull()
    expect(internalParcel(null)).toBeNull()
  })
})

describe('ToolCard', () => {
  it('shows only the summary until it is expanded', () => {
    const wrapper = card()
    expect(wrapper.find('[data-test="tool-card-body"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Checked L&I live')
  })

  it('expands to the envelope: fields, sources and what is unverified', async () => {
    const wrapper = card()
    await wrapper.find('[data-test="tool-card-toggle"]').trigger('click')

    const body = wrapper.find('[data-test="tool-card-body"]')
    expect(body.exists()).toBe(true)
    expect(body.text()).toContain('open_violations')
    expect(body.text()).toContain('violations (live)')
    expect(wrapper.find('[data-test="tool-unverified"]').text()).toContain('what was reported')
  })

  it('shows when each source was read', async () => {
    const wrapper = card()
    await wrapper.find('[data-test="tool-card-toggle"]').trigger('click')
    expect(wrapper.text()).toContain('read 2026-09-05 13:38 UTC')
  })

  it('routes an internal source into the drawer and leaves an external one a link', async () => {
    const wrapper = card()
    await wrapper.find('[data-test="tool-card-toggle"]').trigger('click')

    const external = wrapper.find('[data-test="tool-source-external"]')
    expect(external.attributes('href')).toContain('phl.carto.com')
    expect(external.attributes('target')).toBe('_blank')

    await wrapper.find('[data-test="tool-source-internal"]').trigger('click')
    expect(wrapper.emitted('openLot')?.[0]).toEqual(['phl:191357500'])
  })

  it('announces its expanded state rather than relying on the caret', () => {
    const wrapper = card()
    expect(wrapper.find('[data-test="tool-card-toggle"]').attributes('aria-expanded')).toBe('false')
  })
})

describe('ToolCard nested data', () => {
  it('renders a list of records as a table rather than a wall of JSON', async () => {
    const wrapper = mount(ToolCard, {
      props: {
        call: call({
          name: 'screen_sale',
          envelope: {
            data: {
              sale_date: '2026-09-16',
              lots: [
                { address: '902 S CECIL ST', verdict: 'BID' },
                { address: '4851 N WARNOCK ST', verdict: 'BID' },
              ],
            },
            sources: [],
            unverified: [],
          },
        }),
      },
      global: { plugins: [[Quasar, {}]] },
    })
    await wrapper.find('[data-test="tool-card-toggle"]').trigger('click')

    const nested = wrapper.find('[data-test="tool-nested-table"]')
    expect(nested.exists()).toBe(true)
    expect(nested.text()).toContain('902 S CECIL ST')
    expect(wrapper.find('[data-test="tool-card-body"]').text()).not.toContain('[{"address"')
  })

  it('says how many rows it left out rather than pretending it showed them all', async () => {
    const lots = Array.from({ length: 20 }, (_, i) => ({ address: `LOT ${i}`, verdict: 'PASS' }))
    const wrapper = mount(ToolCard, {
      props: {
        call: call({
          name: 'screen_sale',
          envelope: { data: { lots }, sources: [], unverified: [] },
        }),
      },
      global: { plugins: [[Quasar, {}]] },
    })
    await wrapper.find('[data-test="tool-card-toggle"]').trigger('click')
    expect(wrapper.text()).toContain('and 8 more')
  })
})
