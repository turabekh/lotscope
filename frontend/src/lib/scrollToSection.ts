/**
 * Land on a section of the Lot page and stay there.
 *
 * The evidence sections fetch their own records, so the page grows under a scroll that
 * has already been aimed: scroll once and the section you asked for is a thousand pixels
 * away by the time it has loaded. This re-aims while the layout settles and then stops —
 * beyond that the reader is the one scrolling.
 */

const SETTLE_CHECKS = 4
const SETTLE_INTERVAL_MS = 250
const DRIFT_TOLERANCE_PX = 24
const WAIT_ATTEMPTS = 20
const WAIT_INTERVAL_MS = 100

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * @param id the section's element id
 * @param within the element to search inside; the document when the whole page is the lot.
 *   Scoped, because an id that exists elsewhere on the page is not this lot's section.
 */
export async function scrollToSection(id: string, within?: HTMLElement | null): Promise<boolean> {
  const scope: ParentNode = within ?? document
  let node: Element | null = null
  for (let attempt = 0; attempt < WAIT_ATTEMPTS && node === null; attempt += 1) {
    // Attribute selector rather than #id: the section names are ours, and this needs no
    // escaping to be safe in every environment the components run in.
    node = scope.querySelector(`[id="${id}"]`)
    if (node === null) await sleep(WAIT_INTERVAL_MS)
  }
  if (node === null) return false

  node.scrollIntoView({ block: 'start' })
  const aimed = node.getBoundingClientRect().top
  for (let attempt = 0; attempt < SETTLE_CHECKS; attempt += 1) {
    await sleep(SETTLE_INTERVAL_MS)
    if (Math.abs(node.getBoundingClientRect().top - aimed) > DRIFT_TOLERANCE_PX) {
      node.scrollIntoView({ block: 'start' })
    }
  }
  return true
}
