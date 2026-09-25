import { useRef, useState } from 'react';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import { searchDecisions, SearchRequestError, type SearchDecisionMatch } from '../api/search';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';
import SearchFilters from '../components/SearchFilters';
import {
  countFilters,
  errorsFromApi,
  hasErrors,
  INCOMPLETE_DATE_MESSAGE,
  NO_FILTERS,
  rangeErrors,
  sameFilters,
  toSearchParams,
  type DateGroup,
  type FilterErrors,
  type SearchFilterValues,
} from '../search/filters';

const FILTERS_PANEL_ID = 'search-filters';

const DATE_INPUTS: Record<DateGroup, string[]> = {
  judged: [`${FILTERS_PANEL_ID}-judged-from`, `${FILTERS_PANEL_ID}-judged-to`],
  published: [`${FILTERS_PANEL_ID}-published-from`, `${FILTERS_PANEL_ID}-published-to`],
};

// A half-typed date leaves the input's value empty, which would read as "no
// filter" and quietly widen the search. The browser still knows it is there.
function incompleteDates(form: HTMLFormElement | null): FilterErrors {
  const errors: FilterErrors = {};

  for (const [group, ids] of Object.entries(DATE_INPUTS) as [DateGroup, string[]][]) {
    const incomplete = ids.some((id) => {
      const input = form?.querySelector<HTMLInputElement>(`#${id}`);
      return input?.validity.badInput ?? false;
    });
    if (incomplete) {
      errors[group] = INCOMPLETE_DATE_MESSAGE;
    }
  }

  return errors;
}

const DETAIL_PANEL_ID = 'decision-detail';

// What the detail endpoint identifies a decision by. The case number is not
// enough: one case can have several decisions.
type OpenDecision = { source: string; identifier: string };

const keyOf = (decision: OpenDecision) => `${decision.source}/${decision.identifier}`;

const openButtonId = (decision: OpenDecision) =>
  `open-${keyOf(decision).replace(/[^A-Za-z0-9_-]/g, '-')}`;

// Below this width the two columns stack, the detail under the list.
const STACKED = '(max-width: 1100px)';

const isStacked = () =>
  typeof window.matchMedia === 'function' && window.matchMedia(STACKED).matches;

function HomePage() {
  const [value, setValue] = useState('prescrição intercorrente em execução fiscal');
  const [mode, setMode] = useState<'free' | 'exact'>('free');
  // What the panel shows while it is being edited. A change here never starts a
  // search: only Pesquisar applies it.
  const [filterDraft, setFilterDraft] = useState<SearchFilterValues>(NO_FILTERS);
  // What the results on screen were searched with. Null before the first search.
  const [appliedFilters, setAppliedFilters] = useState<SearchFilterValues | null>(null);
  // Errors found on submit — a half-typed date, or a range the API refused.
  // Backwards ranges are also found live, from the draft itself.
  const [submitErrors, setSubmitErrors] = useState<FilterErrors>({});
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [results, setResults] = useState<SearchDecisionMatch[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  // Only the most recent search may write to the screen. An answer that
  // arrives after a newer search started is dropped.
  const latestSearch = useRef(0);

  // An error from submit wins over the live one, but only where there is one:
  // a period whose submit error was cleared still shows a backwards range.
  const liveErrors = rangeErrors(filterDraft);
  const filterErrors: FilterErrors = {
    judged: submitErrors.judged ?? liveErrors.judged,
    published: submitErrors.published ?? liveErrors.published,
  };
  const appliedCount = appliedFilters ? countFilters(appliedFilters) : 0;
  const hasPendingFilters = appliedFilters !== null && !sameFilters(filterDraft, appliedFilters);

  const updateFilters = (next: SearchFilterValues) => {
    // An error found on submit belongs to the dates as they were then; editing
    // that period clears it.
    setSubmitErrors((current) => ({
      judged:
        next.dateFrom === filterDraft.dateFrom && next.dateTo === filterDraft.dateTo
          ? current.judged
          : undefined,
      published:
        next.publishedFrom === filterDraft.publishedFrom &&
        next.publishedTo === filterDraft.publishedTo
          ? current.published
          : undefined,
    }));
    setFilterDraft(next);

  // The decision shown beside the list. Choosing another item only swaps what
  // the right side shows: the list, and the search behind it, never change.
  const [openDecision, setOpenDecision] = useState<OpenDecision | null>(null);

  const openDetail = (decision: OpenDecision) => {
    setOpenDecision(decision);
    // Stacked, the detail sits below the list, out of sight: bring it in.
    if (isStacked()) {
      requestAnimationFrame(() =>
        document.getElementById(DETAIL_PANEL_ID)?.scrollIntoView({ block: 'start' }),
      );
    }
  };

  // Only reachable stacked, where the list is above: back to the chosen item.
  const backToList = () => {
    if (!openDecision) {
      return;
    }
    const opener = document.getElementById(openButtonId(openDecision));
    opener?.scrollIntoView({ block: 'center' });
    opener?.focus();

  };

  const handleSubmit = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();

    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setErrorMessage('Digite uma expressão para pesquisar.');
      return;
    }

    const blocking = { ...rangeErrors(filterDraft), ...incompleteDates(formRef.current) };

    if (hasErrors(blocking)) {
      setSubmitErrors(blocking);
      setFiltersOpen(true);
      return;
    }

    const filters = filterDraft;
    const searchId = ++latestSearch.current;

    setSubmitErrors({});
    setAppliedFilters(filters);
    setOpenDecision(null);
    setIsLoading(true);
    setErrorMessage(null);
    setTotalResults(null);
    setResults([]);

    try {
      const response = await searchDecisions(toSearchParams(trimmedValue, filters));

      if (searchId !== latestSearch.current) {
        return;
      }

      setTotalResults(response.total);
      setResults(response.results);

      // As in the reference: the first result is open as soon as the list is.
      const [first] = response.results;
      setOpenDecision(first ? { source: first.source, identifier: first.identifier } : null);

      if (response.total === 0) {
        setErrorMessage(
          'Nenhuma decisão foi encontrada para esta expressão. Revise os termos ou tente uma sintaxe diferente.',
        );
      }
    } catch (requestError) {
      if (searchId !== latestSearch.current) {
        return;
      }

      if (requestError instanceof SearchRequestError) {
        const refused = errorsFromApi(requestError.status, requestError.detail);

        if (refused) {
          setSubmitErrors(refused);
          setFiltersOpen(true);
          setErrorMessage(
            'A busca recusou um dos períodos. Revise as datas destacadas nos filtros.',
          );
          return;
        }

        if (requestError.status === 422) {
          setFiltersOpen(true);
          setErrorMessage(
            'Um dos filtros tem um valor que a busca não aceita. Revise as datas e tente novamente.',
          );
          return;
        }
      }

      const message =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'Não foi possível concluir a busca.';

      setErrorMessage(`${message} Tente novamente.`);
    } finally {
      if (searchId === latestSearch.current) {
        setIsLoading(false);
      }
    }
  };

  return (
    <main className="search-page">
      <div className="search-layout">
        <form ref={formRef} className="search-form" onSubmit={handleSubmit} noValidate>
          <div className="legal-search">
            <div className="legal-search__field">
              <MagnifyingGlass size={20} aria-hidden="true" />

              <label className="sr-only" htmlFor="legal-search-input">
                Pesquisar decisões
              </label>

              <input
                id="legal-search-input"
                type="search"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Pesquise um assunto, fundamento ou frase exata"
                autoComplete="off"
                disabled={isLoading}
              />
            </div>

            <div className="legal-search__actions">
              <div className="search-mode" role="group" aria-label="Modalidade da pesquisa">
                <span
                  className="search-mode__indicator"
                  style={{
                    transform: mode === 'free' ? 'translateX(0%)' : 'translateX(100%)',
                  }}
                />

                <button
                  type="button"
                  className={mode === 'free' ? 'is-active' : ''}
                  aria-pressed={mode === 'free'}
                  onClick={() => setMode('free')}
                  disabled={isLoading}
                >
                  Termo livre
                </button>

                <button
                  type="button"
                  className={mode === 'exact' ? 'is-active' : ''}
                  aria-pressed={mode === 'exact'}
                  onClick={() => setMode('exact')}
                  disabled={isLoading}
                >
                  Frase exata
                </button>
              </div>

              <button
                type="button"
                className="filter-button"
                aria-expanded={filtersOpen}
                aria-controls={FILTERS_PANEL_ID}
                onClick={() => setFiltersOpen((open) => !open)}
                disabled={isLoading}
              >
                <SlidersHorizontal size={17} aria-hidden="true" />
                <span>Filtros</span>
                {appliedCount > 0 && (
                  <span className="filter-button__count">
                    {appliedCount}
                    <span className="sr-only"> aplicados</span>
                  </span>
                )}
              </button>

              <button type="submit" className="search-button" disabled={isLoading || !value.trim()}>
                {isLoading ? 'Pesquisando...' : 'Pesquisar'}
              </button>
            </div>
          </div>

          {/* Hidden rather than unmounted, so closing it keeps what was chosen. */}
          <SearchFilters
            id={FILTERS_PANEL_ID}
            values={filterDraft}
            onChange={updateFilters}
            errors={filterErrors}
            hidden={!filtersOpen}
            disabled={isLoading}
          />

          {/* The results below were searched with the applied filters, not with
              what the panel shows now. Said, so they are not read as the new cut. */}
          {hasPendingFilters && !isLoading && (
            <p className="filters-pending" role="status">
              Há alterações nos filtros que ainda não foram aplicadas. Clique em Pesquisar para
              aplicá-las.
            </p>
          )}
        </form>

        {/* Always two columns, as in the reference: the list on the left, the
            decision on the right. */}
        <div className="results-layout">
          <section className="search-results" aria-live="polite">
            {isLoading && (
              <div className="search-state search-state--loading">Carregando resultados...</div>
            )}

            {!isLoading && totalResults !== null && (
              <div className="search-summary">
                <span>Total de resultados:</span>
                <strong>{totalResults}</strong>
              </div>
            )}

            {!isLoading && !errorMessage && totalResults === 0 && (
              <div className="search-state search-state--empty">
                Nenhuma decisão foi encontrada para esta expressão. Revise os termos ou tente uma
                sintaxe diferente.
              </div>
            )}

            {!isLoading && errorMessage && (
              <div className="search-state search-state--error" role="alert">
                <p>{errorMessage}</p>
                <button
                  type="button"
                  className="search-state__retry"
                  onClick={() => handleSubmit()}
                >
                  Tentar novamente
                </button>
              </div>
            )}

            {!isLoading && results.length > 0 && (
              <ul className="result-list">
                {results.map((result) => {
                  const decision = { source: result.source, identifier: result.identifier };
                  const selected = openDecision !== null && keyOf(openDecision) === keyOf(decision);

                  return (
                    <li key={`${result.source}-${result.identifier}`} className="result-item">
                      <DecisionResultCard
                        decision={result}
                        onOpen={() => openDetail(decision)}
                        openButtonId={openButtonId(decision)}
                        selected={selected}
                      />
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Outside the results' live region, so a screen reader is not read the
            whole ementa each time a decision opens. Keyed by the decision, so
            nothing from the previous one shows while the next loads. */}
          {openDecision ? (
            <DecisionDetail
              key={keyOf(openDecision)}
              id={DETAIL_PANEL_ID}
              source={openDecision.source}
              identifier={openDecision.identifier}
              onBack={backToList}
            />
          ) : (
            <aside id={DETAIL_PANEL_ID} className="decision-detail decision-detail--empty">
              <p className="decision-detail__placeholder">
                {isLoading
                  ? 'Carregando resultados...'
                  : 'Pesquise e escolha uma decisão da lista para lê-la aqui.'}
              </p>
            </aside>
          )}
        </div>
      </div>
    </main>
  );
}

export default HomePage;
