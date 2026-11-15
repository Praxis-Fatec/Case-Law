import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, CheckCircle, Info, WarningCircle, X } from '@phosphor-icons/react';
import type { Court } from '../api/courts';
import {
  getComparison,
  getConcentration,
  getCoverage,
  type CourtComparisons,
  type CourtComparison,
  type Coverage,
  type VolumeParams,
} from '../api/indicators';
import { formatCount, formatDateTime } from './coverageFormat';
import { outcomeLabel } from './outcomeFormat';
import { adherenceLabel } from './precedentFormat';
import OutcomeShareChart from './OutcomeShareChart';
import { haveDifferentInstances } from './courtInstance';

type ComparisonState =
  | { status: 'loading' }
  | { status: 'failed'; key: string }
  | {
      status: 'loaded';
      key: string;
      data: CourtComparisons;
      coverage: Coverage | null;
      groups: (number | null)[];
    };

const display = (value: number | null | undefined) =>
  value == null ? 'Indisponível' : formatCount(value);
const categoryCount = (court: CourtComparison | undefined, value: string) =>
  court?.outcomes.find((row) => row.value === value)?.decisions;
const dateLabel = (value: string) => value.split('-').reverse().join('/');
const labels = (value: string) =>
  value === 'unclassified'
    ? 'Não classificado'
    : value === 'unanime'
      ? 'Unânime'
      : value === 'maioria'
        ? 'Por maioria'
        : outcomeLabel(value);

function CoverageNote({
  abbreviation,
  coverage,
  params,
}: {
  abbreviation: string;
  coverage: Coverage | null;
  params: VolumeParams;
}) {
  const court = coverage?.courts.find((item) => item.abbreviation === abbreviation);
  const hasRange = Boolean(court?.first && court.last);
  // Historical bounds are coverage, not evidence of a recent source collection.
  const partial = Boolean(
    hasRange &&
    ((params.date_from && court!.first! > params.date_from) ||
      (params.date_to && court!.last! < params.date_to)),
  );
  const known = hasRange && !partial;
  return (
    <div className="court-comparison__coverage">
      <p
        className={
          known
            ? 'court-comparison__status'
            : 'court-comparison__status court-comparison__status--partial'
        }
      >
        {known ? (
          <CheckCircle size={16} weight="fill" aria-hidden="true" />
        ) : (
          <WarningCircle size={16} weight="fill" aria-hidden="true" />
        )}
        {known
          ? 'Cobertura disponível'
          : partial
            ? 'Cobertura parcial'
            : coverage
              ? 'Cobertura não informada'
              : 'Cobertura indisponível'}
      </p>
      <p>
        <strong>Cobertura: </strong>
        {hasRange
          ? `${dateLabel(court!.first!)} a ${dateLabel(court!.last!)}`
          : 'Período não informado'}
      </p>
      <p className="court-comparison__collection">
        Última coleta da base: {formatDateTime(coverage?.updated_at) ?? 'não informada'}
      </p>
    </div>
  );
}

function CourtCharts({ court, maxValue }: { court: CourtComparison; maxValue: number }) {
  return (
    <>
      <p className="court-comparison__denominator">
        Base dos percentuais: {display(court.total)} decisões deste tribunal.
      </p>
      {(
        [
          ['outcomes', 'Resultado'],
          ['deliberations', 'Deliberação'],
          ['adherences', 'Aderência'],
        ] as const
      ).map(([field, title]) => (
        <section
          key={field}
          className="court-comparison__chart"
          aria-label={`${title} do ${court.abbreviation}`}
        >
          <h4>{title}</h4>
          <OutcomeShareChart
            horizontal
            maxValue={maxValue}
            labelFor={
              field === 'adherences'
                ? (value) => (value === 'unclassified' ? 'Sem citação' : adherenceLabel(value))
                : labels
            }
            outcomes={court[field].map((item) => ({
              outcome: item.value ?? 'unclassified',
              decisions: item.decisions,
              share: item.share,
            }))}
          />
          {!court[field].some((item) => item.decisions !== null && item.decisions > 0) && (
            <p>Sem classificações disponíveis.</p>
          )}
        </section>
      ))}
      <p className="court-comparison__explanation">
        Uma decisão pode tratar precedentes de formas diferentes e entrar em mais de uma categoria
        de aderência.
      </p>
    </>
  );
}

export default function CourtComparisonPanel({
  params,
  courts,
  onClose,
  onDocuments,
  returnFocus,
}: {
  params: VolumeParams;
  courts: Court[];
  onClose: () => void;
  onDocuments: (court: string, count: number) => void;
  returnFocus: HTMLElement | null;
}) {
  const available = [
    ...new Set([...(params.tribunal ?? []), ...courts.map((court) => court.abbreviation)]),
  ];
  const [choices, setChoices] = useState<[string, string]>(['', '']);
  const selected = [
    choices[0] || available[0] || '',
    choices[1] || available.find((court) => court !== (choices[0] || available[0])) || '',
  ];
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ComparisonState>({ status: 'loading' });
  const dialog = useRef<HTMLDialogElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const requestKey = JSON.stringify({ ...params, tribunal: selected.filter(Boolean) });

  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    close.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      returnFocus?.focus();
    };
  }, [returnFocus]);

  useEffect(() => {
    const request = JSON.parse(requestKey) as VolumeParams;
    if (!request.tribunal?.length) return;
    const controller = new AbortController();
    const options = { signal: controller.signal };
    Promise.all([
      getComparison(request, options),
      getCoverage(options).catch(() => null),
      Promise.all(
        request.tribunal.map(async (court) => {
          try {
            const result = await getConcentration(
              { ...request, tribunal: [court] },
              { ...options, limit: 1 },
            );
            const dimension = result.judging_bodies;
            return dimension.other?.groups == null
              ? null
              : dimension.groups.length + dimension.other.groups;
          } catch {
            return null;
          }
        }),
      ),
    ]).then(
      ([data, coverage, groups]) => {
        if (!controller.signal.aborted)
          setState({ status: 'loaded', key: requestKey, data, coverage, groups });
      },
      () => {
        if (!controller.signal.aborted) setState({ status: 'failed', key: requestKey });
      },
    );
    return () => controller.abort();
  }, [requestKey, attempt]);

  const loaded = state.status === 'loaded' && state.key === requestKey ? state : null;
  const failed = state.status === 'failed' && state.key === requestKey;
  const columns = selected.map((court) =>
    loaded?.data.courts.find((item) => item.abbreviation === court),
  );
  const maxValue = Math.max(1, ...columns.map((court) => court?.total ?? 0));
  const canCompare = selected.every(Boolean);
  const ready = Boolean(loaded) && canCompare;
  const metricRows = [
    { label: 'Decisões encontradas', values: columns.map((court) => court?.total) },
    { label: 'Órgãos julgadores', values: selected.map((_, index) => loaded?.groups[index]) },
    { label: 'Recursos negados', values: columns.map((court) => categoryCount(court, 'negado')) },
  ];

  return createPortal(
    <dialog
      ref={dialog}
      className="court-comparison"
      aria-modal="true"
      aria-labelledby="court-comparison-title"
      aria-describedby="court-comparison-context"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="court-comparison__surface">
        <header className="court-comparison__header">
          <h2 id="court-comparison-title">Comparar tribunais</h2>
          <p id="court-comparison-context">Mesma expressão, período e filtros nos dois lados</p>
          <button
            ref={close}
            type="button"
            className="court-comparison__close"
            aria-label="Fechar comparação de tribunais"
            onClick={onClose}
          >
            <X size={23} />
          </button>
        </header>
        <div className="court-comparison__selectors">
          {selected.map((court, index) => (
            <div key={index}>
              <label htmlFor={`comparison-court-${index}`}>
                Tribunal {index === 0 ? 'A' : 'B'}
              </label>
              <select
                id={`comparison-court-${index}`}
                value={court}
                onChange={(event) => {
                  const value = event.target.value;
                  setChoices([
                    index === 0 ? value : selected[0],
                    index === 1 ? value : selected[1],
                  ]);
                }}
              >
                <option value="" disabled>
                  Selecione um tribunal
                </option>
                {available.map((value) => (
                  <option key={value} value={value} disabled={value === selected[1 - index]}>
                    {value}
                  </option>
                ))}
              </select>
              {court && (
                <CoverageNote
                  abbreviation={court}
                  coverage={loaded?.coverage ?? null}
                  params={params}
                />
              )}
            </div>
          ))}
        </div>
        {haveDifferentInstances(selected[0], selected[1]) && (
          <p className="court-comparison__instance-warning" role="note" aria-live="polite">
            <WarningCircle size={18} aria-hidden="true" />
            <span>
              Instâncias diferentes: julgam recursos distintos, por isso taxas de provimento não
              medem rigor.
            </span>
          </p>
        )}
        {!canCompare && (
          <p role="status" className="court-comparison__notice">
            Selecione dois tribunais diferentes para comparar. A lista de tribunais pode estar
            indisponível ou conter apenas um tribunal.
          </p>
        )}
        {canCompare && !ready && !failed && (
          <p role="status" className="court-comparison__notice">
            Carregando comparação…
          </p>
        )}
        {failed && (
          <div role="alert" className="court-comparison__notice">
            <p>
              Não foi possível carregar a comparação. Os dados estão indisponíveis, não são
              contagens zero.
            </p>
            <button
              type="button"
              onClick={() => {
                setState({ status: 'loading' });
                setAttempt((value) => value + 1);
              }}
            >
              Tentar novamente
            </button>
          </div>
        )}
        {ready && (
          <>
            <div
              className="court-comparison__table"
              role="table"
              aria-label="Critérios por tribunal"
            >
              <div className="court-comparison__row court-comparison__row--heading" role="row">
                <span role="columnheader">Critério</span>
                {selected.map((court) => (
                  <span key={court} role="columnheader">
                    {court}
                  </span>
                ))}
              </div>
              {metricRows.map((row) => (
                <div key={row.label} className="court-comparison__row" role="row">
                  <span role="rowheader">{row.label}</span>
                  {row.values.map((value, index) => (
                    <strong key={selected[index]} role="cell">
                      <span className="court-comparison__mobile-court">{selected[index]}: </span>
                      {display(value)}
                    </strong>
                  ))}
                </div>
              ))}
            </div>
            <details className="court-comparison__details">
              <summary>Mais critérios</summary>
              <p className="court-comparison__explanation">
                Escala comum aos dois tribunais: número de decisões, a partir de zero. Percentuais
                sobre a base de cada tribunal.
              </p>
              <div className="court-comparison__columns">
                {columns.map((court, index) => (
                  <section key={selected[index]} aria-label={`Indicadores do ${selected[index]}`}>
                    <h3>{selected[index]}</h3>
                    {court && court.total !== null && court.total > 0 ? (
                      <CourtCharts court={court} maxValue={maxValue} />
                    ) : (
                      <p className="court-comparison__notice">
                        {court?.total === 0
                          ? 'Nenhuma decisão corresponde à expressão e aos filtros aplicados neste tribunal.'
                          : 'Os indicadores deste tribunal estão indisponíveis.'}
                      </p>
                    )}
                  </section>
                ))}
              </div>
            </details>
            <div className="court-comparison__actions">
              {columns.map((court, index) => (
                <div key={selected[index]}>
                  {court?.total === 0 && (
                    <p className="court-comparison__empty">
                      Nenhuma decisão neste recorte. Revise a expressão ou os filtros.
                    </p>
                  )}
                  <button
                    type="button"
                    disabled={court?.total == null || court.total === 0}
                    onClick={() =>
                      court?.total != null && onDocuments(selected[index], court.total)
                    }
                  >
                    Ver documentos do {selected[index]} <ArrowRight size={17} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </>
        )}
        <footer className="court-comparison__footer">
          <Info size={17} aria-hidden="true" />
          <p>
            Os valores refletem os documentos disponíveis. Diferenças de cobertura e frequência não
            representam relevância jurídica.
          </p>
        </footer>
      </div>
    </dialog>,
    document.body,
  );
}
