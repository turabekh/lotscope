import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CorrectionsQueue from '@/components/CorrectionsQueue.vue'
import { api } from '@/lib/api'
import type { CorrectionRecord } from '@/lib/types'

function makeRecord(overrides: Partial<CorrectionRecord> = {}): CorrectionRecord {
  return {
    id: 7,
    parcel_number: 'phl:99900002',
    market_code: 'phl',
    reported_by: 3,
    section: 'valuation',
    field_name: 'value_estimate_low',
    verdict_computed_at: '2026-07-29T08:00:00Z',
    field_status: 'estimated',
    source_label: 'RTT transfers',
    source_as_of: '2026-07-01T00:00:00Z',
    attachment_ref: null,
    description: 'The land value looks far too high for this block.',
    status: 'open',
    resolution: null,
    resolved_at: null,
    created_at: '2026-08-01T00:00:00Z',
    ...overrides,
  }
}

function mountQueue() {
  return mount(CorrectionsQueue, { global: { plugins: [[Quasar, {}]] } })
}

describe('CorrectionsQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the evidence captured with the report', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([makeRecord()])
    const wrapper = mountQueue()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('phl:99900002')
    expect(text).toContain('valuation')
    expect(text).toContain('field state estimated')
    expect(text).toContain('source RTT transfers')
  })

  it('says when the evidence was not recorded rather than leaving it blank', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([
      makeRecord({ field_status: null, source_label: null }),
    ])
    const wrapper = mountQueue()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('field state unrecorded')
    expect(text).toContain('source unrecorded')
  })

  it('sends the operator note with the new status', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([makeRecord()])
    const triage = vi.spyOn(api, 'triageCorrection').mockResolvedValue(makeRecord())
    const wrapper = mountQueue()
    await flushPromises()

    await wrapper.find('[data-test="correction-note-7"]').setValue('Recomputed the comps.')
    await wrapper.find('[data-test="correction-resolve-7"]').trigger('click')
    await flushPromises()

    expect(triage).toHaveBeenCalledWith(7, {
      status: 'resolved',
      resolution: 'Recomputed the comps.',
    })
  })

  it('sends no resolution when the operator leaves the note empty', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([makeRecord()])
    const triage = vi.spyOn(api, 'triageCorrection').mockResolvedValue(makeRecord())
    const wrapper = mountQueue()
    await flushPromises()

    await wrapper.find('[data-test="correction-reject-7"]').trigger('click')
    await flushPromises()

    expect(triage).toHaveBeenCalledWith(7, { status: 'rejected', resolution: null })
  })

  it('never claims a change was made when a report is rejected', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([
      makeRecord({ status: 'rejected', resolution: 'The assessment matches OPA.' }),
    ])
    const wrapper = mountQueue()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Reason:')
    expect(text).not.toContain('Resolution:')
    expect(text.toLowerCase()).not.toContain('corrected')
  })

  it('reports a failed update without implying the record changed', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([makeRecord()])
    vi.spyOn(api, 'triageCorrection').mockRejectedValue(new Error('boom'))
    const wrapper = mountQueue()
    await flushPromises()

    await wrapper.find('[data-test="correction-resolve-7"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="corrections-error"]').text()).toContain('Nothing was changed.')
  })

  it('offers no triage actions on a record already closed', async () => {
    vi.spyOn(api, 'getCorrectionQueue').mockResolvedValue([makeRecord({ status: 'resolved' })])
    const wrapper = mountQueue()
    await flushPromises()

    expect(wrapper.find('[data-test="correction-resolve-7"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="correction-reject-7"]').exists()).toBe(false)
  })
})
