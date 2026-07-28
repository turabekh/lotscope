import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import LegalPage from '@/pages/LegalPage.vue'
import { api } from '@/lib/api'
import { routes } from '@/router'
import type { PolicyDocument, PolicySummary } from '@/lib/types'

const INDEX: PolicySummary[] = [
  {
    slug: 'terms',
    title: 'Terms of Service',
    published: false,
    version: null,
    effective_date: null,
  },
  {
    slug: 'privacy',
    title: 'Privacy Policy',
    published: true,
    version: '1.0',
    effective_date: '2026-08-01T00:00:00Z',
  },
]

function doc(): PolicyDocument {
  return {
    slug: 'privacy',
    title: 'Privacy Policy',
    body_markdown: 'First paragraph.\n\nSecond paragraph.',
    version: '1.0',
    effective_date: '2026-08-01T00:00:00Z',
    published_at: '2026-07-28T00:00:00Z',
  }
}

async function mountLegal(slug: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push({ name: 'legal', params: { slug } })
  await router.isReady()
  const wrapper = mount(LegalPage, {
    global: {
      plugins: [router, [Quasar, {}]],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('LegalPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'getPolicyIndex').mockResolvedValue(INDEX)
  })

  it('shows no substitute text when a policy is unpublished', async () => {
    vi.spyOn(api, 'getPolicy').mockRejectedValue(new Error('not published'))
    const wrapper = await mountLegal('terms')
    const notice = wrapper.find('[data-test="policy-unpublished"]')
    expect(notice.text()).toContain('has not been published yet')
    expect(notice.text()).toContain('mistaken for the real terms')
    expect(wrapper.find('.doc-body').exists()).toBe(false)
  })

  it('renders published copy with its version and effective date', async () => {
    vi.spyOn(api, 'getPolicy').mockResolvedValue(doc())
    const wrapper = await mountLegal('privacy')
    expect(wrapper.find('[data-test="policy-meta"]').text()).toContain('Version 1.0')
    const blocks = wrapper.findAll('.doc-body')
    expect(blocks).toHaveLength(2)
    expect(blocks[0]!.text()).toBe('First paragraph.')
  })

  it('marks unpublished policies in the index', async () => {
    vi.spyOn(api, 'getPolicy').mockResolvedValue(doc())
    const wrapper = await mountLegal('privacy')
    const index = wrapper.find('[data-test="policy-index"]')
    expect(index.text()).toContain('Terms of Service')
    expect(index.text()).toContain('not published')
  })
})
