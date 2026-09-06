/**
 * Hand a lot to the Analyst.
 *
 * The parcel travels as a query parameter and the Analyst page turns it into the opening
 * question, so the conversation starts with the lot already in context rather than the
 * buyer retyping an address they were just looking at.
 */
export function askAboutLotQuery(parcelNumber: string, address: string | null) {
  return { about: parcelNumber, label: address ?? parcelNumber }
}

export function openingQuestionFor(label: string): string {
  return `What's the story on ${label}?`
}

/**
 * The opening question for a set handed over from Deals. One lot reads as a question about
 * that lot; several read as a question about the group, because "what's the story on A, B
 * and C?" is what a person would actually ask.
 */
export function openingQuestionForMany(labels: string[]): string {
  if (labels.length === 0) return ''
  if (labels.length === 1) return openingQuestionFor(labels[0])
  const list = labels.slice(0, -1).join(', ')
  return `Where do these stand — ${list} and ${labels[labels.length - 1]}?`
}
