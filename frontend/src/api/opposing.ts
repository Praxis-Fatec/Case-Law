import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, SearchRequestError } from './search';
import { apiHeaders } from './token';

/**
 * The decisions that may contradict the one being read — `RF23`.
 *
 * The reason travels with every entry, because the reason is the point: two
 * decisions citing the same precedent, one following it and the other
 * departing from it or distinguishing it. A list of "contrary decisions" that
 * does not say where they diverge is noise with the face of analysis.
 *
 * Unlike `related.ts`, an unavailable answer here is not an empty one. The
 * endpoint answers 503 where the table is not published, and the caller has to
 * keep the two apart: telling a reader there is no contradiction when nobody
 * looked is the one wrong answer this screen cannot afford.
 */

export type Disagreement = {
  court: string;
  kind: string;
  number: number | null;
  // What the decision being read did with the precedent, and what the other
  // one did: `seguiu`, `afastou` or `distinguiu`.
  this_decision: string;
  other_decision: string;
};

// Everything `DecisionBase` carries, which the detail screen already knows how
// to read, plus the evidence for the indication.
export type Contrary = {
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
  // Orders the list, by the same cosine `RF20` uses. Not a measure of
  // disagreement, which is why nothing shows it as a number.
  similarity: number | null;
  terms: number | null;
  opposite_outcome: boolean;
  disagreements: Disagreement[];
};

export type Opposition = {
  results: Contrary[];
  // Where the indication comes from, in the API's own words. `RF23` requires
  // it to be told apart from a settled legal conclusion.
  basis: string | null;
};

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const number = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const flag = (value: unknown) => (typeof value === 'boolean' ? value : null);

export function readDisagreement(value: unknown): Disagreement | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const court = text(row.court);
  const kind = text(row.kind);
  const here = text(row.this_decision);
  const there = text(row.other_decision);

  // Without both adherences there is no disagreement to state, and a precedent
  // named without them is the noise this feature exists to avoid.
  if (!court || !kind || !here || !there) {
    return null;
  }

  return {
    court,
    kind,
    number: number(row.number),
    this_decision: here,
    other_decision: there,
  };
}

export function readContrary(value: unknown): Contrary | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const source = text(row.source);
  const identifier = text(row.identifier);

  // Without both there is no address to open and no card worth showing.
  if (!source || !identifier) {
    return null;
  }

  const disagreements = Array.isArray(row.disagreements)
    ? row.disagreements.map(readDisagreement).filter((item): item is Disagreement => item !== null)
    : [];

  // An entry whose reason did not survive the reading is dropped whole. The
  // backend never produces one; what reaches here is an older API or a
  // mangled answer, and either way the card would be an indication with no
  // stated reason.
  if (disagreements.length === 0) {
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
    opposite_outcome: flag(row.opposite_outcome) ?? false,
    disagreements,
  };
}

export function readOpposition(body: unknown): Opposition {
  const raw = (body ?? {}) as Record<string, unknown>;

  return {
    results: Array.isArray(raw.results)
      ? raw.results.map(readContrary).filter((row): row is Contrary => row !== null)
      : [],
    basis: text(raw.basis),
  };
}

export async function getOpposingDecisions(
  source: string,
  identifier: string,
  options: { signal?: AbortSignal; limit?: number } = {},
): Promise<Opposition> {
  assertApiConfiguration();

  const path = `/decisions/${encodeURIComponent(source)}/${encodeURIComponent(identifier)}/opposing`;
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

  return readOpposition(await response.json());
}
