import { useState } from 'react';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';
import { searchDecisions, type SearchDecisionMatch } from '../api/search';
import DecisionDetail from '../components/DecisionDetail';
import DecisionResultCard from '../components/DecisionResultCard';

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
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [results, setResults] = useState<SearchDecisionMatch[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
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

    // A new search replaces the list the open decision came from.
    setOpenDecision(null);
    setIsLoading(true);
    setErrorMessage(null);
    setTotalResults(null);
    setResults([]);

    try {
      const response = await searchDecisions({ q: trimmedValue, page: 1, page_size: 20 });
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
      const message =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'Não foi possível concluir a busca.';

      setErrorMessage(`${message} Tente novamente.`);
    } finally {
      setIsLoading(false);
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
