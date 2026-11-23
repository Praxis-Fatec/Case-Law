import { apiBaseUrl, assertApiConfiguration } from './client';
import { readDetail, SearchRequestError } from './search';
import { apiHeaders } from './token';

// The laws a decision applied, parsed by the pipeline out of the fixed format
// the STJ publishes them in. One entry per article cited, so a reference that
// names six articles arrives as six entries.
//
// `sphere` and `act_type` are the court's own three-letter codes, never
// translated by the API: expanding them is this layer's job, and only for the
// codes whose meaning is settled.
export type CitedLegislation = {
  sphere: string | null;
  act_type: string | null;
  number: number | null;
  year: number | null;
  article: string | null;
  paragraphs: string[];
  items: string[];
  letters: string[];
  recognised: boolean;
  raw: string | null;
};

const text = (value: unknown) => (typeof value === 'string' && value.trim() ? value.trim() : null);

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null;

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(text).filter((item): item is string => item !== null) : [];

export function readCitedLegislation(value: unknown): CitedLegislation | null {
  const row = (value ?? {}) as Record<string, unknown>;
  const raw = text(row.raw);
  const actType = text(row.act_type);

  // An entry with neither a readable act nor the court's own text has nothing
  // to show: it would be a blank line claiming the decision applied something.
  if (!actType && !raw) {
    return null;
  }

  return {
    sphere: text(row.sphere),
    act_type: actType,
    number: count(row.number),
    year: count(row.year),
    article: text(row.article),
    paragraphs: strings(row.paragraphs),
    items: strings(row.items),
    letters: strings(row.letters),
    // Absent reads as unrecognised, which is the cautious way round: it shows
    // the court's text instead of claiming a reading that did not happen.
    recognised: row.recognised === true,
    raw,
  };
}

export function readCitedLegislationList(body: unknown): CitedLegislation[] {
  const raw = (body ?? {}) as Record<string, unknown>;

  return Array.isArray(raw.results)
    ? raw.results.map(readCitedLegislation).filter((row): row is CitedLegislation => row !== null)
    : [];
}

// Enrichment, never the critical path: a failure here shows the decision
// without the legislation block rather than an error page.
export async function getCitedLegislation(
  source: string,
  identifier: string,
  options: { signal?: AbortSignal } = {},
): Promise<CitedLegislation[]> {
  assertApiConfiguration();

  const target = new URL(
    `${apiBaseUrl}/decisions/${encodeURIComponent(source)}/${encodeURIComponent(
      identifier,
    )}/legislation`,
    window.location.origin,
  );

  const response = await fetch(target.toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new SearchRequestError(response.status, await readDetail(response));
  }

  return readCitedLegislationList(await response.json());
}
