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
    const observers: Array<() => void> = []
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(callback: () => void) {
          observers.push(callback)
        }
        observe() {}
        disconnect() {}
      },
    )
    const root = document.createElement('div')
    const node = sectionIn(root, 'violations')
    const scrolled = vi.fn()
    node.scrollIntoView = scrolled

    const done = scrollToSection('violations', root)
    await vi.advanceTimersByTimeAsync(0)
    // The evidence sections finish loading and the page changes size underneath.
    observers.forEach((fire) => fire())
    await vi.advanceTimersByTimeAsync(2000)
    await done

    // Once to land, and again for the growth that moved it.
    expect(scrolled.mock.calls.length).toBeGreaterThan(1)
    vi.unstubAllGlobals()
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
