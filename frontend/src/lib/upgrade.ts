export type UpgradeCap =
  | 'parcel_views'
  | 'ask'
  | 'saved_search'
  | 'leads'
  | 'export'
  | 'letters'
  | 'buyer_intel'

export interface UpgradeCopy {
  headline: string
  detail: string
}

export const UPGRADE_COPY: Record<UpgradeCap, UpgradeCopy> = {
  parcel_views: {
    headline: "You've reached the free limit of 4 parcel verdicts per day.",
    detail: 'Pro and Investor unlock unlimited verdicts, full comps, risk flags, and value ranges.',
  },
  ask: {
    headline: "You've used today's 10 AI questions.",
    detail: 'Pro raises Ask the Parcel to 200 questions per day; Investor is unlimited.',
  },
  saved_search: {
    headline: 'Free includes 1 saved search.',
    detail: 'Pro includes 50 saved searches; Investor is unlimited.',
  },
  leads: {
    headline: 'Free previews 8 motivated-seller leads.',
    detail: 'Pro returns 200 leads; Investor returns 1,000 with CSV export.',
  },
  export: {
    headline: 'CSV export is a paid feature.',
    detail: 'Pro exports up to 2,000 rows per file (10 files/month); Investor is unlimited at 10,000 rows.',
  },
  letters: {
    headline: 'Direct-mail letters are a paid feature.',
    detail: 'Pro and Investor generate print-ready owner letters from your leads and saved searches.',
  },
  buyer_intel: {
    headline: 'Cash-buyer intelligence is an Investor feature.',
    detail:
      'Investor reveals who is actively buying vacant lots near your parcels — their purchase ' +
      'history, activity, and mailing address where recorded.',
  },
}
