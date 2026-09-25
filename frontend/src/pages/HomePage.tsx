import { useRef, useState } from 'react';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import {
  DEFAULT_ORDER,
  searchDecisions,
  type SearchDecisionMatch,
  type SearchOrder,
} from '../api/search';
import DecisionResultCard from '../components/DecisionResultCard';
import ResultsSort from '../components/ResultsSort';

// What the results on screen were searched with. Changing the order searche
// this again, never whatever is being typed in the box and not yet applied.
type AppliedSearch = { q: string; order: SearchOrder };

const PAGE_SIZE = 20;

// The one place a request is built from the applied search. Paging, when it
// comes, asks for another page of this same search — same expression, same
// order — so a page can never be read in a different order than the first.
const requestFor = (search: AppliedSearch, page = 1) => ({
  q: search.q,
  page,
  page_size: PAGE_SIZE,
  order: search.order,
});

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
  const [applied, setApplied] = useState<AppliedSearch | null>(null);
  // Only the most recent search may write to the screen: an answer that
  // arrives after the order was changed again is dropped.
  const latestSearch = useRef(0);

  // `failure`, when given, replaces the usual message: a failed reorder says so,
  // rather than reading like the search itself went wrong.
  const runSearch = async (search: AppliedSearch, failure?: string) => {
    const searchId = ++latestSearch.current;

    setApplied(search);
    setIsLoading(true);
    setErrorMessage(null);
    // Nothing from the previous answer stays up while the new one loads, so
    // old results never pass for the new order.
    setTotalResults(null);
    setResults([]);

    try {
      // Every new order or expression starts on the first page.
      const response = await searchDecisions(requestFor(search));

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

      const message =
        failure ??
        (requestError instanceof Error && requestError.message
          ? requestError.message
          : 'Não foi possível concluir a busca.');

      setErrorMessage(`${message} Tente novamente.`);
    } finally {
      if (searchId === latestSearch.current) {
        setIsLoading(false);
      }
    }
  };

  const handleSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();

    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setErrorMessage('Digite uma expressão para pesquisar.');
      return;
    }

    // A new expression keeps the order already chosen.
    void runSearch({ q: trimmedValue, order: applied?.order ?? DEFAULT_ORDER });
  };

  const changeOrder = (order: SearchOrder) => {
    // Choosing the order already applied asks the API for nothing.
    if (!applied || order === applied.order) {
      return;
    }

    void runSearch({ ...applied, order }, 'Não foi possível reordenar os resultados.');
  };

  // Retries what failed — the applied search — not an edit left in the box.
  const retry = () => {
    if (applied) {
      void runSearch(applied);
    } else {
      handleSubmit();
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

        {/* Beside the total and above the list. Kept up while a new order loads
            or fails, so it can be changed back or retried. Outside the live
            region below, so choosing an order is not read out as a new result. */}
        {applied && (
          <div className="results-toolbar">
            <div className="search-summary" aria-live="polite">
              {!isLoading && totalResults !== null && (
                <>
                  <span>Total de resultados:</span>
                  <strong>{totalResults}</strong>
                </>
              )}
            </div>
            <ResultsSort value={applied.order} onChange={changeOrder} disabled={isLoading} />
          </div>
        )}

        <section className="search-results" aria-live="polite">
          {isLoading && (
            <div className="search-state search-state--loading">Carregando resultados...</div>
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
              <button type="button" className="search-state__retry" onClick={retry}>
                Tentar novamente
              </button>
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
