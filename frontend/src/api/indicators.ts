import { apiBaseUrl, assertApiConfiguration } from './client';

// What `/indicators/coverage` answers: the base as a whole, never a search. It
// takes no parameter, so no expression, filter, order or page can reach it.
//
// Every field the screen shows may come back null here: `null` means the
// answer did not carry it in a readable form, which is not the same as zero.

export type CourtCoverage = {
  abbreviation: string;
  name: string | null;
  documents: number | null;
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
  documents: number | null;
  first: string | null;
  last: string | null;
  // Largest first, as the API orders them.
  courts: CourtCoverage[];
  state: LoadState | null;
  // When the most recent successful load finished, in UTC: the collection's
  // date, not a decision's.
  updated_at: string | null;
};

export class CoverageRequestError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Coverage request failed with status ${status}`);
    this.name = 'CoverageRequestError';
    this.status = status;
  }
}

const LOAD_STATES: readonly string[] = ['loaded', 'all_loads_failed', 'never_loaded'];

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;

function readCourt(value: unknown): CourtCoverage | null {
  const court = (value ?? {}) as Record<string, unknown>;
  const abbreviation = text(court.abbreviation);

  // A row with no court to name is no row at all.
  if (!abbreviation) {
    return null;
  }

  return {
    abbreviation,
    name: text(court.name),
    documents: count(court.documents),
    first: text(court.first),
    last: text(court.last),
  };
}

// Read field by field, so one field the screen cannot use leaves the others
// standing instead of taking the whole answer down.
export function readCoverage(body: unknown): Coverage {
  const raw = (body ?? {}) as Record<string, unknown>;
  const state = text(raw.state);

  return {
    documents: count(raw.documents),
    first: text(raw.first),
    last: text(raw.last),
    courts: Array.isArray(raw.courts)
      ? raw.courts.map(readCourt).filter((court): court is CourtCoverage => court !== null)
      : [],
    state: state && LOAD_STATES.includes(state) ? (state as LoadState) : null,
    updated_at: text(raw.updated_at),
  };
}

export async function getCoverage(options: { signal?: AbortSignal } = {}): Promise<Coverage> {
  assertApiConfiguration();

  // Nothing is appended: the coverage is the same whatever is being searched.
  const url = new URL(`${apiBaseUrl}/indicators/coverage`, window.location.origin);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new CoverageRequestError(response.status);
  }

  return readCoverage(await response.json());
}
