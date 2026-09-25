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

// What the results on screen were searched with. Changing the order searches
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
        <form className="legal-search" onSubmit={handleSubmit} noValidate>
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
              aria-label="Abrir filtros"
              disabled={isLoading}
            >
              <SlidersHorizontal size={17} aria-hidden="true" />
              <span>Filtros</span>
              <span className="filter-button__count">4</span>
            </button>

            <button type="submit" className="search-button" disabled={isLoading || !value.trim()}>
              {isLoading ? 'Pesquisando...' : 'Pesquisar'}
            </button>
          </div>
        </form>

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

          {!isLoading && results.length > 0 && (
            <ul className="result-list">
              {results.map((result) => (
                <li key={`${result.source}-${result.identifier}`} className="result-item">
                  <DecisionResultCard decision={result} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

export default HomePage;
