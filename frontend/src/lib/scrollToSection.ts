/**
 * Land on a section of the Lot page and stay there.
 *
 * The evidence sections fetch their own records and the map loads its tiles, so the page
 * grows under a scroll that has already been aimed: scroll once and the section you asked
 * for is a thousand pixels away by the time everything has arrived. Two earlier attempts
 * stopped too soon — a one-second timer, then a resize watcher whose idle window expired
 * before the first fetch came back — and production landed in the verdict either way.
 *
 * So this simply holds its aim for a few seconds: check often, re-aim when the section has
 * drifted, and stop the moment the reader scrolls for themselves. Predictable beats clever
 * here; nothing about the page's loading is being inferred.
 */

const HOLD_MS = 6000
const CHECK_MS = 300
const DRIFT_TOLERANCE_PX = 24
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

  let handOver = false
  const release = (): void => {
    handOver = true
  }
  const events = ['wheel', 'touchstart', 'keydown'] as const
  for (const event of events) window.addEventListener(event, release, { passive: true })

  try {
    node.scrollIntoView({ block: 'start' })
    const target = node.getBoundingClientRect().top
    const checks = Math.floor(HOLD_MS / CHECK_MS)
    for (let check = 0; check < checks && !handOver; check += 1) {
      await sleep(CHECK_MS)
      if (handOver) break
      if (Math.abs(node.getBoundingClientRect().top - target) > DRIFT_TOLERANCE_PX) {
        node.scrollIntoView({ block: 'start' })
      }
    }
  } finally {
    for (const event of events) window.removeEventListener(event, release)
  }
  return true
}
