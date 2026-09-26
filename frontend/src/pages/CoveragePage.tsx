import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, Info } from '@phosphor-icons/react';

import { getCoverage } from '../api/indicators';
import CourtCoverageTable from '../components/CourtCoverageTable';
import CoverageSummary from '../components/CoverageSummary';
import { formatCount, type CoverageState } from '../components/coverageFormat';

export const COVERAGE_PATH = '/cobertura';

// What the entry carries when the page was opened from inside the app.
export type CoverageEntry = { fromApp?: boolean } | null;

function CoveragePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const fromApp = (location.state as CoverageEntry)?.fromApp === true;
  const [state, setState] = useState<CoverageState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  // Asked each time the page opens, and of the base alone: nothing from the
  // search — its expression, filters, order, page or results — goes with it,
  // so a narrow or empty search never makes the base look smaller.
  useEffect(() => {
    // Leaving the page, or retrying, abandons the request in flight, so a late
    // answer never replaces the one on screen.
    const controller = new AbortController();
    let active = true;

    getCoverage({ signal: controller.signal }).then(
      (coverage) => {
        if (active) {
          setState({ status: 'loaded', coverage });
        }
      },
      () => {
        if (active) {
          setState({ status: 'failed' });
        }
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [attempt]);

  const retry = () => {
    setState({ status: 'loading' });
    setAttempt((current) => current + 1);
  };

  const documents = state.status === 'loaded' ? state.coverage.documents : null;

  // The search lives above the routes, so its results, filters and page are
  // still there. Opened from the app, Back returns to the exact entry — the
  // list or the decision the reader was on. Opened from a link, there is none
  // behind it, so the way back is to the search, forward.
  const backToSearch = () => {
    if (fromApp) {
      navigate(-1);
    } else {
      navigate('/');
    }
  };

  return (
    <main className="coverage-page">
      <div className="coverage-layout">
        <header className="coverage-header">
          <div className="coverage-header__text">
            <p className="coverage-eyebrow">Informações do sistema</p>
            <h1 className="coverage-title">Cobertura da base</h1>
            <p className="coverage-lead">
              Consulte o alcance de toda a base disponível na plataforma. Estes dados não mudam com
              os termos ou filtros de uma pesquisa.
            </p>
          </div>

          <button type="button" className="coverage-back" onClick={backToSearch}>
            <ArrowLeft size={15} aria-hidden="true" />
            Voltar à pesquisa
          </button>
        </header>

        {/* A failure is said as one, never shown as an empty base. */}
        {state.status === 'failed' && (
          <div className="search-state search-state--error coverage-error" role="alert">
            <p>
              Não foi possível carregar a cobertura da base. Verifique a conexão e tente novamente.
            </p>
            <button type="button" className="search-state__retry" onClick={retry}>
              Tentar novamente
            </button>
          </div>
        )}

        <CoverageSummary state={state} />

        <section className="coverage-courts" aria-labelledby="coverage-courts-title">
          <div className="coverage-courts__heading">
            <div>
              <p className="coverage-eyebrow">Fontes integradas</p>
              <h2 id="coverage-courts-title" className="coverage-courts__title">
                Cobertura por tribunal
              </h2>
            </div>
            {documents !== null && (
              <p className="coverage-courts__total">
                {formatCount(documents)} {documents === 1 ? 'documento' : 'documentos'} no total
              </p>
            )}
          </div>

          <CourtCoverageTable state={state} />
        </section>

        <aside className="coverage-note" aria-labelledby="coverage-note-title">
          <Info size={17} aria-hidden="true" className="coverage-note__icon" />
          <div>
            <h2 id="coverage-note-title" className="coverage-note__title">
              Como interpretar esta página
            </h2>
            <p className="coverage-note__text">
              A cobertura informa o que existe na base inteira, não o resultado de uma pesquisa: os
              termos, filtros e páginas de uma busca não alteram estes números. As datas de registro
              são as das próprias decisões (a do julgamento ou, sem ela, a da publicação); a última
              atualização é quando a coleta mais recente terminou. Um tribunal pesquisável tem
              documentos na base e pode ser usado nos filtros da pesquisa.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}

export default CoveragePage;
