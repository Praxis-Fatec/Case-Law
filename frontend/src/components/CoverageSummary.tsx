import type { ReactNode } from 'react';
import { CheckCircle, Database, WarningCircle } from '@phosphor-icons/react';

import type { Coverage } from '../api/indicators';
import {
  courtsPhrase,
  formatCount,
  formatDateTime,
  isEmptyBase,
  NOT_INFORMED,
  UNAVAILABLE,
  type CoverageState,
} from './coverageFormat';
import { formatDate } from './decisionFormat';

type Situation = { label: string; ok: boolean } | null;

// "Disponível" needs both: a load that finished and documents it left. An
// answer that arrived is not, on its own, a base that is available.
function situationOf(coverage: Coverage): Situation {
  switch (coverage.state) {
    case 'loaded':
      if (coverage.documents === null) {
        return null;
      }
      return coverage.documents > 0
        ? { label: 'Disponível', ok: true }
        : { label: 'Sem documentos', ok: false };
    case 'all_loads_failed':
      return { label: 'Nenhuma coleta concluída', ok: false };
    case 'never_loaded':
      return { label: 'Ainda não coletada', ok: false };
    default:
      return null;
  }
}

// A base with no documents has no period: said, not left looking like a date
// the answer forgot to send.
function periodOf(coverage: Coverage, value: string | null): string {
  if (isEmptyBase(coverage)) {
    return 'Sem registros';
  }
  return formatDate(value) ?? NOT_INFORMED;
}

// Only a finished load has a time. Without one, the reason is said rather than
// a missing value.
function updatedOf(coverage: Coverage): string {
  const updated = formatDateTime(coverage.updated_at);
  if (updated) {
    return updated;
  }
  return coverage.state === 'all_loads_failed' || coverage.state === 'never_loaded'
    ? 'Nenhuma coleta concluída'
    : NOT_INFORMED;
}

// The courts are counted from the rows. No rows while documents exist, or
// while their number is unknown, is a list that did not come — not no courts.
function courtsOf(coverage: Coverage): string {
  if (coverage.courts.length > 0 || isEmptyBase(coverage)) {
    return courtsPhrase(coverage.courts.length);
  }
  return 'tribunais não informados';
}

// A value still on its way is a blank bar, not a number; one that could not be
// read says so in the same place, so the grid keeps its shape either way.
function Pending({ loading, large = false }: { loading: boolean; large?: boolean }) {
  if (loading) {
    return (
      <span className={`coverage-skeleton${large ? ' coverage-skeleton--large' : ''}`}>
        <span className="sr-only">Carregando</span>
      </span>
    );
  }

  return <span className="coverage-unavailable">{UNAVAILABLE}</span>;
}

// The same muted face for a field the answer did not carry.
function Value({ text }: { text: string }) {
  const missing = text === NOT_INFORMED || text === 'Sem registros';
  return missing ? <span className="coverage-unavailable">{text}</span> : <>{text}</>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="coverage-summary__field">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function CoverageSummary({ state }: { state: CoverageState }) {
  const loading = state.status === 'loading';
  const coverage = state.status === 'loaded' ? state.coverage : null;
  const pending = <Pending loading={loading} />;

  const total = coverage && formatCount(coverage.documents);
  const situation = coverage && situationOf(coverage);
  const SituationIcon = situation?.ok ? CheckCircle : WarningCircle;

  return (
    <section className="coverage-summary" aria-label="Resumo da base" aria-busy={loading}>
      <div className="coverage-summary__total">
        <Database size={22} aria-hidden="true" className="coverage-summary__icon" />
        <p className="coverage-summary__total-label">Total de documentos públicos</p>
        <p className="coverage-summary__total-value">
          {coverage ? (
            (total ?? <span className="coverage-unavailable">{NOT_INFORMED}</span>)
          ) : (
            <Pending loading={loading} large />
          )}
        </p>
        <p className="coverage-summary__courts">{coverage ? courtsOf(coverage) : ' '}</p>
      </div>

      <dl className="coverage-summary__details">
        <Field label="Primeiro registro">
          {coverage ? <Value text={periodOf(coverage, coverage.first)} /> : pending}
        </Field>
        <Field label="Registro mais recente">
          {coverage ? <Value text={periodOf(coverage, coverage.last)} /> : pending}
        </Field>
        <Field label="Última atualização">
          {coverage ? <Value text={updatedOf(coverage)} /> : pending}
        </Field>
        <Field label="Situação da base">
          {!coverage ? (
            pending
          ) : situation ? (
            <span className={`coverage-status${situation.ok ? '' : ' coverage-status--warning'}`}>
              <SituationIcon size={15} weight="fill" aria-hidden="true" />
              {situation.label}
            </span>
          ) : (
            <Value text={NOT_INFORMED} />
          )}
        </Field>
      </dl>
    </section>
  );
}

export default CoverageSummary;
