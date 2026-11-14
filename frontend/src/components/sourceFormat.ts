import type { SourceStatus } from '../api/indicators';
import { formatDate } from './decisionFormat';

// What the section has to show. The sources are asked apart from the coverage,
// so they load and fail on their own.
export type SourcesState =
  { status: 'loading' } | { status: 'failed' } | { status: 'loaded'; sources: SourceStatus[] };

export const CONTENT_LABELS: Record<string, string> = {
  decisao: 'Decisões',
  precedente: 'Precedentes',
  doutrina: 'Doutrina',
};

// Four readings of one source, and they are not interchangeable. "Nunca
// coletada" is a connector nobody turned on; "todas as coletas falharam" is one
// to go and look at; "bloqueada" is the source refusing us, which is nobody's
// defect here. Only the first keeps what it has.
export type SourceReading = 'coletando' | 'falhando' | 'bloqueada' | 'nunca' | 'desconhecida';

export function readingOf(source: SourceStatus): SourceReading {
  if (source.state === null) {
    return 'desconhecida';
  }

  if (source.state === 'never_loaded') {
    return 'nunca';
  }

  if (source.state === 'all_loads_failed') {
    return 'falhando';
  }

  if (source.availability === 'bloqueada') {
    return 'bloqueada';
  }

  return source.last_attempt_failed ? 'falhando' : 'coletando';
}

export const READING_LABELS: Record<SourceReading, string> = {
  coletando: 'Coletando',
  falhando: 'Última tentativa falhou',
  bloqueada: 'Coleta bloqueada pela fonte',
  nunca: 'Nunca coletada',
  desconhecida: 'Estado não informado',
};

// The period, written at the precision the source's own data supports. The
// BDJur publishes a year, so its date carries a 1 January nobody published:
// writing it out would be inventing a day, which is exactly what the RF16
// forbids.
export function periodOf(source: SourceStatus): string | null {
  if (source.precision === 'nenhuma' || source.precision === null) {
    return null;
  }

  if (source.precision === 'ano') {
    const first = source.first?.slice(0, 4);
    const last = source.last?.slice(0, 4);

    if (!first || !last) {
      return null;
    }

    return first === last ? first : `${first} – ${last}`;
  }

  const first = formatDate(source.first);
  const last = formatDate(source.last);

  if (!first || !last) {
    return null;
  }

  return first === last ? first : `${first} – ${last}`;
}
