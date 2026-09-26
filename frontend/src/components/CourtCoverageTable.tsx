import { CheckCircle } from '@phosphor-icons/react';

import { formatCount, UNAVAILABLE, type CoverageState } from './coverageFormat';
import { formatDate } from './decisionFormat';

const COLUMNS = [
  'Tribunal',
  'Documentos',
  'Início da cobertura',
  'Registro mais recente',
  'Status',
];

// Said in the table's own body, so the header keeps the composition while the
// rows are on their way, did not come, or do not exist yet.
function stateMessage(state: CoverageState): string | null {
  if (state.status === 'loading') {
    return 'Carregando a cobertura por tribunal...';
  }

  if (state.status === 'unavailable') {
    return 'A cobertura por tribunal está indisponível no momento.';
  }

  return state.coverage.courts.length === 0
    ? 'Nenhum tribunal tem documentos na base ainda.'
    : null;
}

function CourtCoverageTable({ state }: { state: CoverageState }) {
  const message = stateMessage(state);
  const courts = state.status === 'loaded' ? state.coverage.courts : [];

  return (
    <div className="court-coverage" aria-busy={state.status === 'loading'}>
      <table className="court-coverage__table">
        <caption className="sr-only">Cobertura por tribunal</caption>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {message ? (
            <tr>
              <td colSpan={COLUMNS.length} className="court-coverage__message">
                {message}
              </td>
            </tr>
          ) : (
            courts.map((court) => (
              <tr key={court.abbreviation}>
                <th scope="row" className="court-coverage__court">
                  <span className="court-coverage__abbreviation">{court.abbreviation}</span>
                  <span className="court-coverage__name">{court.name}</span>
                </th>
                <td>{formatCount(court.documents)}</td>
                <td>{formatDate(court.first) ?? UNAVAILABLE}</td>
                <td>{formatDate(court.last) ?? UNAVAILABLE}</td>
                <td>
                  {/* The API has no status per court. What it does say is that
                      the court has decisions in the base, which is exactly what
                      makes it searchable — so that, and nothing more. */}
                  <span className="coverage-status">
                    <CheckCircle size={15} weight="fill" aria-hidden="true" />
                    Pesquisável
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default CourtCoverageTable;
