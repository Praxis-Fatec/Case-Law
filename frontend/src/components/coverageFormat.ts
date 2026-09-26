import type { Coverage } from '../api/indicators';
import { normalizeText } from './decisionFormat';

// What the page has to show. Until the base answers, every value is either on
// its way or unavailable — never a placeholder number that could be read.
export type CoverageState =
  { status: 'loading' } | { status: 'unavailable' } | { status: 'loaded'; coverage: Coverage };

export const UNAVAILABLE = 'Indisponível';

const COUNT = new Intl.NumberFormat('pt-BR');

export const formatCount = (value: number) => COUNT.format(value);

// The load finished at an instant, sent in UTC. Shown on Brasília's clock, the
// one the reader's day runs on, whatever zone the browser is set to.
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

  return count === 1 ? 'em 1 tribunal integrado' : `em ${formatCount(count)} tribunais integrados`;
}
