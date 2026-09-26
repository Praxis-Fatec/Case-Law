import type { Coverage } from '../api/indicators';
import { normalizeText } from './decisionFormat';

export { NOT_INFORMED } from './decisionFormat';

// What the page has to show. While the base is being asked, or when it could
// not be, no value is shown — never a zero that could be read as the answer.
export type CoverageState =
  { status: 'loading' } | { status: 'failed' } | { status: 'loaded'; coverage: Coverage };

// The request failed: nothing is known. Not the same as a field the answer did
// not carry, which is "Não informado".
export const UNAVAILABLE = 'Indisponível';

// Zero documents is an answer: the base is there and holds nothing yet. A
// count the answer did not carry says nothing about it either way.
export const isEmptyBase = (coverage: Coverage) => coverage.documents === 0;

const COUNT = new Intl.NumberFormat('pt-BR');

export const formatCount = (value: number | null): string | null =>
  value === null ? null : COUNT.format(value);

// The load finished at an instant, sent in UTC. Shown on Brasília's clock, the
// one the reader's day runs on, whatever zone the browser is set to. A date
// alone (`formatDate`) is a day, not an instant, and is never shifted.
const DATE_TIME = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export function formatDateTime(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  const parsed = new Date(normalized);

  return Number.isNaN(parsed.getTime()) ? null : DATE_TIME.format(parsed);
}

export function courtsPhrase(count: number): string {
  if (count === 0) {
    return 'nenhum tribunal integrado';
  }

  return count === 1 ? 'em 1 tribunal integrado' : `em ${COUNT.format(count)} tribunais integrados`;
}
