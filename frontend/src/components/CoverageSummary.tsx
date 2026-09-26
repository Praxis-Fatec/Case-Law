import type { ReactNode } from 'react';
import { CheckCircle, Database, WarningCircle } from '@phosphor-icons/react';

import type { LoadState } from '../api/indicators';
import {
  courtsPhrase,
  formatCount,
  formatDateTime,
  UNAVAILABLE,
  type CoverageState,
} from './coverageFormat';
import { formatDate } from './decisionFormat';

// Only `loaded` says the data is there to be read. The other two are said as
// what they are, not rounded to "available" or left blank.
const SITUATION: Record<LoadState, { label: string; ok: boolean }> = {
  loaded: { label: 'Disponível', ok: true },
  all_loads_failed: { label: 'Nenhuma coleta concluída', ok: false },
  never_loaded: { label: 'Ainda não coletada', ok: false },
};

// A value still on its way is a blank bar, not a number; one that did not come
// says so in the same place, so the grid keeps its shape either way.
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

  const text = (value: string | null) => value ?? <Pending loading={loading} />;
  const situation = coverage ? SITUATION[coverage.state] : null;
  const SituationIcon = situation?.ok ? CheckCircle : WarningCircle;

  return (
    <section className="coverage-summary" aria-label="Resumo da base" aria-busy={loading}>
      <div className="coverage-summary__total">
        <Database size={22} aria-hidden="true" className="coverage-summary__icon" />
        <p className="coverage-summary__total-label">Total de documentos públicos</p>
        <p className="coverage-summary__total-value">
          {coverage ? formatCount(coverage.documents) : <Pending loading={loading} large />}
        </p>
        <p className="coverage-summary__courts">
          {coverage ? courtsPhrase(coverage.courts.length) : ' '}
        </p>
      </div>

      <dl className="coverage-summary__details">
        <Field label="Primeiro registro">{text(coverage && formatDate(coverage.first))}</Field>
        <Field label="Registro mais recente">{text(coverage && formatDate(coverage.last))}</Field>
        <Field label="Última atualização">
          {text(coverage && formatDateTime(coverage.updated_at))}
        </Field>
        <Field label="Situação da base">
          {situation ? (
            <span className={`coverage-status${situation.ok ? '' : ' coverage-status--warning'}`}>
              <SituationIcon size={15} weight="fill" aria-hidden="true" />
              {situation.label}
            </span>
          ) : (
            <Pending loading={loading} />
          )}
        </Field>
      </dl>
    </section>
  );
}

export default CoverageSummary;
