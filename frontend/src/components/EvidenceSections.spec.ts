import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DeedsEvidence from '@/components/DeedsEvidence.vue'
import DelinquencyEvidence from '@/components/DelinquencyEvidence.vue'
import SheriffEvidence from '@/components/SheriffEvidence.vue'
import ViolationsEvidence from '@/components/ViolationsEvidence.vue'
import { api } from '@/lib/api'
import type { AnalystEnvelope } from '@/lib/types'

const PARCEL = 'phl:000000001'

function envelope(overrides: Partial<AnalystEnvelope>): AnalystEnvelope {
  return { data: {}, sources: [], unverified: [], ...overrides }
}

async function mountWith(
  component: Parameters<typeof mount>[0],
  payload: AnalystEnvelope,
  reject = false,
) {
  const spy = vi.spyOn(api, 'getEvidence')
  if (reject) spy.mockRejectedValue(new Error('nope'))
  else spy.mockResolvedValue(payload)
  const wrapper = mount(component, {
    props: { parcelNumber: PARCEL },
    global: { plugins: [Quasar] },
  })
  await new Promise((resolve) => setTimeout(resolve, 0))
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('DeedsEvidence', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('shows each recorded transfer with its parties and consideration', async () => {
    const wrapper = await mountWith(
      DeedsEvidence,
      envelope({
        data: {
          deeds: [
            {
              sale_date: '2019-04-02',
              consideration: 42000,
              document_type: 'DEED',
              document_id: '53000001',
              grantor: 'PRIOR OWNER',
              grantee: 'JANE DOE',
            },
          ],
        },
        sources: [
          {
            name: 'rtt_summary',
            url: null,
            fetched_at: null,
            ingested_at: '2026-09-05T04:20:00Z',
            computed_at: null,
          },
        ],
      }),
    )

    const table = wrapper.find('[data-test="deeds-table"]')
    expect(table.exists()).toBe(true)
    expect(table.text()).toContain('PRIOR OWNER')
    expect(table.text()).toContain('JANE DOE')
    expect(table.text()).toContain('$42,000')
    // No public URL for the recorder row, so the source names itself and when it was read.
    expect(wrapper.find('[data-test="evidence-sources"]').text()).toContain('ingested 2026-09-05')
  })

  it('says a transfer carries no party name rather than leaving the cell blank', async () => {
    const wrapper = await mountWith(
      DeedsEvidence,
      envelope({
        data: {
          deeds: [
            {
              sale_date: null,
              consideration: null,
              document_type: 'DEED',
              document_id: null,
              grantor: null,
              grantee: null,
            },
          ],
        },
      }),
    )
    expect(wrapper.find('[data-test="deeds-table"]').text()).toContain('no party name recorded')
  })

  it('does not report a load failure as an empty deed chain', async () => {
    const wrapper = await mountWith(DeedsEvidence, envelope({}), true)
    expect(wrapper.find('[data-test="deeds-unavailable"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="deeds-empty"]').exists()).toBe(false)
  })
})

describe('ViolationsEvidence', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('separates what is open from what is only on record', async () => {
    const wrapper = await mountWith(
      ViolationsEvidence,
      envelope({
        data: {
          posture: { violations_on_record: 6, open_violations: 2 },
          violations: [
            {
              event_date: '2024-06-01',
              status: 'OPEN',
              case_status: 'IN VIOLATION',
              description: 'Vacant lot not maintained',
              unsafe: false,
              imminently_dangerous: true,
            },
          ],
        },
        unverified: ['L&I records what was reported and inspected.'],
      }),
    )

    expect(wrapper.find('[data-test="violations-lede"]').text()).toBe(
      '6 violations on record, 2 are open.',
    )
    expect(wrapper.find('[data-test="violation-imminently-dangerous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="evidence-unverified"]').text()).toContain(
      'reported and inspected',
    )
  })

  it('does not report a load failure as a clean record', async () => {
    const wrapper = await mountWith(ViolationsEvidence, envelope({}), true)
    expect(wrapper.find('[data-test="violations-unavailable"]').text()).toContain('not a clean')
    expect(wrapper.find('[data-test="violations-lede"]').exists()).toBe(false)
  })
})

describe('DelinquencyEvidence', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('names the debtor and repeats the attribution rather than implying the owner owes it', async () => {
    const wrapper = await mountWith(
      DelinquencyEvidence,
      envelope({
        data: {
          tax: {
            is_delinquent: true,
            // Decimals arrive as strings, exactly as the Analyst receives them.
            total_due: '8400.00',
            principal_due: '5100.00',
            years_owed: 3,
            lien_count: 1,
            as_of_date: '2026-01-31',
            delinquency_owner: 'PRIOR OWNER',
          },
          attribution: 'The debt is recorded against PRIOR OWNER, not the current owner JANE DOE.',
        },
      }),
    )

    expect(wrapper.find('[data-test="delinquency-posture"]').text()).toContain('$8,400')
    expect(wrapper.find('[data-test="delinquency-debtor"]').text()).toBe('PRIOR OWNER')
    expect(wrapper.find('[data-test="delinquency-attribution"]').text()).toContain('PRIOR OWNER')
  })

  it('says no tax record is on file rather than showing a clean posture', async () => {
    const wrapper = await mountWith(DelinquencyEvidence, envelope({ data: { tax: {} } }))
    expect(wrapper.find('[data-test="delinquency-posture"]').text()).toBe(
      'No tax record is on file for this parcel.',
    )
    expect(wrapper.find('[data-test="delinquency-facts"]').exists()).toBe(false)
  })
})

describe('SheriffEvidence', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('marks a postponed listing whose date is still ahead as scheduled', async () => {
    const wrapper = await mountWith(
      SheriffEvidence,
      envelope({
        data: {
          listings: [
            {
              case_number: '2301-1234',
              sale_type: 'TAX',
              sale_date: '2026-09-16',
              status: 'Postponed',
              opening_bid: 1200,
              plaintiff: 'CITY OF PHILADELPHIA',
              is_scheduled: true,
            },
          ],
          changes: [{ observed_at: '2026-08-30T00:00:00Z', summary: 'Sale date moved to Sep 16.' }],
        },
      }),
    )

    const table = wrapper.find('[data-test="sheriff-table"]')
    expect(table.text()).toContain('2301-1234')
    expect(wrapper.find('[data-test="sheriff-scheduled"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="sheriff-changes"]').text()).toContain('Sale date moved')
  })

  it('says no listing is on file, which is itself the answer', async () => {
    const wrapper = await mountWith(SheriffEvidence, envelope({ data: { listings: [] } }))
    expect(wrapper.find('[data-test="sheriff-empty"]').text()).toContain('No sheriff-sale listing')
  })
})
