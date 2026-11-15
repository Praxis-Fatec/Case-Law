import { CheckCircle, Prohibit, Question, WarningCircle } from '@phosphor-icons/react';

import type { SourceStatus } from '../api/indicators';
import { formatCount, formatDateTime, NOT_INFORMED } from './coverageFormat';
import {
  CONTENT_LABELS,
  periodOf,
  READING_LABELS,
  readingOf,
  type SourceReading,
  type SourcesState,
} from './sourceFormat';

const COLUMNS = ['Fonte', 'Conteúdo', 'Itens', 'Período coberto', 'Última coleta', 'Estado'];

const ICONS: Record<SourceReading, typeof CheckCircle> = {
  coletando: CheckCircle,
  falhando: WarningCircle,
  bloqueada: Prohibit,
  nunca: Question,
  desconhecida: Question,
};

function stateMessage(state: SourcesState): string | null {
  if (state.status === 'loading') {
    return 'Carregando o estado das fontes...';
  }

  if (state.status === 'failed') {
    return 'O estado das fontes está indisponível no momento.';
  }

  // No rows is not an empty catalogue: the answer did not carry the sources.
  return state.sources.length === 0 ? 'O estado das fontes não foi informado.' : null;
}

function Missing() {
  return <span className="coverage-unavailable">{NOT_INFORMED}</span>;
}

// A failure says when it last worked, because that is the date the data on
// screen is from. A source that never worked has no such date, and says that
// instead of leaving the cell blank.
function Collected({ source }: { source: SourceStatus }) {
  const collected = formatDateTime(source.last_collection);
  const attempted = formatDateTime(source.last_attempt);

  if (!collected) {
    return (
      <span className="source-status__never">
        {attempted ? `Nenhuma concluída · tentativa em ${attempted}` : 'Nenhuma coleta registrada'}
      </span>
    );
  }

  return (
    <>
      <span className="source-status__collected">{collected}</span>
      {source.last_attempt_failed && attempted && (
        <span className="source-status__attempt">Tentativa em {attempted} falhou</span>
      )}
    </>
  );
}

function SourceStatusTable({ state }: { state: SourcesState }) {
  const message = stateMessage(state);
  const sources = state.status === 'loaded' ? state.sources : [];

  return (
    <div className="source-status" aria-busy={state.status === 'loading'}>
      <table className="source-status__table">
        <caption className="sr-only">Estado de cada fonte e data da última coleta</caption>
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
              <td colSpan={COLUMNS.length} className="source-status__message">
                {message}
              </td>
            </tr>
          ) : (
            sources.map((source) => {
              const reading = readingOf(source);
              const Icon = ICONS[reading];
              const period = periodOf(source);

              return (
                <tr key={source.code}>
                  <th scope="row" className="source-status__source">
                    <span className="source-status__name">{source.name ?? source.code}</span>
                    <span className="source-status__code">{source.code}</span>
                  </th>
                  <td>
                    {source.content ? (
                      (CONTENT_LABELS[source.content] ?? source.content)
                    ) : (
                      <Missing />
                    )}
                  </td>
                  <td>
                    {formatCount(source.items) ?? <Missing />}
                    {/* Undated items are named, not dropped: the period above
                        is computed over the dated ones only. */}
                    {source.undated_items !== null && source.undated_items > 0 && (
                      <span className="source-status__undated">
                        {formatCount(source.undated_items)} sem data
                      </span>
                    )}
                  </td>
                  <td>{period ?? <span className="source-status__never">Sem período</span>}</td>
                  <td>
                    <Collected source={source} />
                  </td>
                  <td>
                    <span className={`source-status__reading source-status__reading--${reading}`}>
                      <Icon size={13} weight="fill" aria-hidden="true" />
                      {READING_LABELS[reading]}
                    </span>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default SourceStatusTable;
