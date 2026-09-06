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
