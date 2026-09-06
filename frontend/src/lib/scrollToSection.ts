/**
 * Land on a section of the Lot page and stay there.
 *
 * The evidence sections fetch their own records and the map loads its tiles, so the page
 * grows under a scroll that has already been aimed: scroll once and the section you asked
 * for is a thousand pixels away by the time everything has arrived. Aiming again on a
 * short timer was not enough either — on production the growth outlasted a one-second
 * window and the drawer settled inside the verdict.
 *
 * So this watches the page actually change size and re-aims each time it does, until the
 * layout has been still for a moment or the budget runs out. Then it stops: past that,
 * the reader is the one scrolling.
 */

const STILL_MS = 700
const BUDGET_MS = 8000
const WAIT_ATTEMPTS = 20
const WAIT_INTERVAL_MS = 100

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function findSection(id: string, scope: ParentNode): Promise<Element | null> {
  for (let attempt = 0; attempt < WAIT_ATTEMPTS; attempt += 1) {
    // Attribute selector rather than #id: the section names are ours, and this needs no
    // escaping to be safe in every environment the components run in.
    const node = scope.querySelector(`[id="${id}"]`)
    if (node !== null) return node
    await sleep(WAIT_INTERVAL_MS)
  }
  return null
}

/**
 * @param id the section's element id
 * @param within the element to search inside; the document when the whole page is the lot.
 *   Scoped, because an id that exists elsewhere on the page is not this lot's section.
 */
export async function scrollToSection(id: string, within?: HTMLElement | null): Promise<boolean> {
  const scope: ParentNode = within ?? document
  const node = await findSection(id, scope)
  if (node === null) return false

  const aim = (): void => node.scrollIntoView({ block: 'start' })
  aim()

  const watched = within ?? document.body
  if (typeof ResizeObserver === 'undefined') {
    await sleep(STILL_MS)
    aim()
    return true
  }

  await new Promise<void>((resolve) => {
    let still: ReturnType<typeof setTimeout>
    const stop = (): void => {
      clearTimeout(still)
      clearTimeout(budget)
      observer.disconnect()
      resolve()
    }
    const observer = new ResizeObserver(() => {
      aim()
      clearTimeout(still)
      still = setTimeout(stop, STILL_MS)
    })
    const budget = setTimeout(stop, BUDGET_MS)
    still = setTimeout(stop, STILL_MS)
    observer.observe(watched)
    for (const section of Array.from(watched.querySelectorAll('section[id]'))) {
      observer.observe(section)
    }
  })
  return true
}
