// What `/indicators/coverage` answers: the base as a whole, never a search. It
// takes no parameter, so no expression, filter or page can reach it.

export type CourtCoverage = {
  abbreviation: string;
  name: string;
  documents: number;
  // `YYYY-MM-DD`: the decisions' own dates (judgement, or publication when the
  // judgement date is missing), not when they were collected.
  first: string | null;
  last: string | null;
};

// Whether a load ever finished here. Read this rather than the absence of a
// date: a new environment and a broken pipeline both have no `updated_at`.
export type LoadState = 'loaded' | 'all_loads_failed' | 'never_loaded';

export type Coverage = {
  // Zero before the first load, which is an answer rather than an error.
  documents: number;
  first: string | null;
  last: string | null;
  // Largest first.
  courts: CourtCoverage[];
  state: LoadState;
  // When the most recent successful load finished, in UTC: the collection's
  // date, not a decision's.
  updated_at: string | null;
};
