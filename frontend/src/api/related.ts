import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, SearchRequestError } from './search';
import { apiHeaders } from './token';

/**
 * The decisions the base found to treat the same subject as one being read.
 *
 * Suggestions, not links the court made. `RF20` requires the method to be
 * stated and a computed relation to be told apart from an official one, so the
 * answer carries the method and the screen says it out loud.
 */

// Everything `DecisionBase` carries, which is what the detail screen already
// knows how to read, plus the evidence for the suggestion.
export type Neighbour = {
  source: string;
  identifier: string;
  court: string;
  case_number: string | null;
  judging_body: string | null;
  reporting_judge: string | null;
  decided_on: string;
  small_claims: boolean;
  source_url: string;
  source_url_reachable: boolean | null;
  source_url_shared: boolean;
  deliberation: string | null;
  // Orders the list. It is not a measure of agreement: two decisions on one
  // subject can settle it in opposite directions and still score high.
  similarity: number | null;
  terms: number | null;
  // Word stems, rarest first. `stems.ts` spells them out; nothing shows them
  // as they arrive.
  matched_on: string[];
};

export type Relation = {
  results: Neighbour[];
  // How the relation was arrived at, in the API's own words.
  method: string | null;
};

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const number = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const flag = (value: unknown) => (typeof value === 'boolean' ? value : null);

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(text).filter((item): item is string => item !== null) : [];

export function readNeighbour(value: unknown): Neighbour | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const source = text(row.source);
  const identifier = text(row.identifier);

  // Without both there is no address to open and no card worth showing.
  if (!source || !identifier) {
    return null;
  }

  return {
    source,
    identifier,
    court: text(row.court) ?? '',
    case_number: text(row.case_number),
    judging_body: text(row.judging_body),
    reporting_judge: text(row.reporting_judge),
    decided_on: text(row.decided_on) ?? '',
    small_claims: flag(row.small_claims) ?? false,
    source_url: text(row.source_url) ?? '',
    source_url_reachable: flag(row.source_url_reachable),
    source_url_shared: flag(row.source_url_shared) ?? false,
    deliberation: text(row.deliberation),
    similarity: number(row.similarity),
    terms: number(row.terms),
    matched_on: strings(row.matched_on),
  };
}

export function readRelation(body: unknown): Relation {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    results: Array.isArray(raw.results)
      ? raw.results.map(readNeighbour).filter((row): row is Neighbour => row !== null)
      : [],
    method: text(raw.method),
  };
}

// Enrichment, never the critical path: the decision is already on screen when
// this is asked, and an environment whose base predates the weights answers an
// empty list rather than an error.
export async function getRelatedDecisions(
  source: string,
  identifier: string,
  options: { signal?: AbortSignal; limit?: number } = {},
): Promise<Relation> {
  assertApiConfiguration();

  const path = `/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}/related`;
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin);

  if (options.limit) {
    url.searchParams.set('limit', String(options.limit));
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readRelation(await response.json());
}
