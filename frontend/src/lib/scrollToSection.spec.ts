import { describe, expect, it, vi } from 'vitest'

import { scrollToSection } from '@/lib/scrollToSection'

function sectionIn(root: HTMLElement, id: string): HTMLElement {
  const node = document.createElement('section')
  node.id = id
  root.appendChild(node)
  return node
}

describe('scrollToSection', () => {
  it('re-aims when the page grows under the scroll it already made', async () => {
    vi.useFakeTimers()
    const root = document.createElement('div')
    const node = sectionIn(root, 'violations')
    let top = 0
    node.getBoundingClientRect = () => ({ top }) as DOMRect
    const scrolled = vi.fn(() => {
      top = 0
    })
    node.scrollIntoView = scrolled

    const done = scrollToSection('violations', root)
    // The evidence sections load and push the target down the page.
    top = 900
    await vi.advanceTimersByTimeAsync(1200)
    await done

    // Once to land, and again for each settle check that found it had drifted.
    expect(scrolled.mock.calls.length).toBeGreaterThan(1)
    vi.useRealTimers()
  })

  it('gives up rather than scrolling to a section this lot does not have', async () => {
    vi.useFakeTimers()
    const root = document.createElement('div')
    const promise = scrollToSection('nothing-here', root)
    await vi.advanceTimersByTimeAsync(3000)
    expect(await promise).toBe(false)
    vi.useRealTimers()
  })

  it('never scrolls an element outside the root it was given', async () => {
    vi.useFakeTimers()
    const outside = document.createElement('section')
    outside.id = 'violations'
    outside.scrollIntoView = vi.fn()
    document.body.appendChild(outside)
    const root = document.createElement('div')

    const promise = scrollToSection('violations', root)
    await vi.advanceTimersByTimeAsync(3000)

    expect(await promise).toBe(false)
    expect(outside.scrollIntoView).not.toHaveBeenCalled()
    outside.remove()
    vi.useRealTimers()
  })
})
