import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CircleNotch, Info, X } from '@phosphor-icons/react';
import {
  deleteSavedSearch,
  getSavedSearch,
  listSavedSearches,
  SavedSearchError,
  savedSearchFailure,
  type SavedSearch,
} from '../api/savedSearches';
import {
  resumeSavedSearch,
  SavedSearchResumeError,
  SAVED_SEARCHES_TRIGGER,
  type ResumedSearch,
} from '../search/savedSearches';
import { formatDateTime } from './coverageFormat';
import { useDialog } from './useDialog';
import SavedDecisionsList from './SavedDecisionsList';
import { useSavedDecisions } from '../search/savedDecisionsContext';

type ListState =
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; searches: SavedSearch[] };

export default function SavedSearchesDrawer({
  onClose,
  onResume,
  onCount,
  onRemoved,
}: {
  onClose: () => void;
  onResume: (search: ResumedSearch) => void;
  onCount: (count: number) => void;
  onRemoved: (id: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<'searches' | 'decisions'>('searches');
  const bookmarks = useSavedDecisions();
  const action = useRef<AbortController | null>(null);
  const [state, setState] = useState<ListState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState<{ id: string; kind: 'resume' | 'delete' } | null>(null);
  const [error, setError] = useState<{ id?: string; message: string } | null>(null);
  useDialog(dialog, SAVED_SEARCHES_TRIGGER);
  useEffect(() => {
    const controller = new AbortController();
    listSavedSearches(controller.signal).then(
      (searches) => {
        if (!controller.signal.aborted) {
          setState({ status: 'loaded', searches });
          onCount(searches.length);
        }
      },
      (failure) => {
        if (!controller.signal.aborted)
          setState({ status: 'failed', message: savedSearchFailure(failure) });
      },
    );
    return () => controller.abort();
  }, [attempt, onCount]);
  useEffect(() => () => action.current?.abort(), []);
  const removeFromList = (id: string) => {
    if (state.status !== 'loaded') return;
    const searches = state.searches.filter((item) => item.id !== id);
    setState({ status: 'loaded', searches });
    onCount(searches.length);
    onRemoved(id);
  };
  const run = async (item: SavedSearch, kind: 'resume' | 'delete') => {
    if (action.current) return;
    const controller = new AbortController();
    action.current = controller;
    setBusy({ id: item.id, kind });
    setError(null);
    try {
      if (kind === 'resume') {
        const current = await getSavedSearch(item.id, controller.signal);
        if (!controller.signal.aborted) onResume(resumeSavedSearch(current));
      } else {
        await deleteSavedSearch(item.id, controller.signal);
        if (!controller.signal.aborted) removeFromList(item.id);
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        if (failure instanceof SavedSearchError && failure.status === 404) removeFromList(item.id);
        setError({
          id: failure instanceof SavedSearchError && failure.status === 404 ? undefined : item.id,
          message:
            failure instanceof SavedSearchResumeError
              ? failure.message
              : savedSearchFailure(failure),
        });
      }
    } finally {
      if (!controller.signal.aborted) {
        action.current = null;
        setBusy(null);
      }
    }
  };
  const searches = state.status === 'loaded' ? state.searches : [];
  return createPortal(
    <dialog
      ref={dialog}
      className="saved-items"
      aria-labelledby="saved-items-title"
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="saved-items__surface">
        <header className="saved-items__header">
          <p className="saved-items__eyebrow">Memória de trabalho</p>
          <h2 id="saved-items-title">Itens salvos</h2>
          <button
            type="button"
            className="saved-items__close"
            aria-label="Fechar itens salvos"
            onClick={onClose}
            autoFocus
          >
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        <div className="saved-items__tabs" role="group" aria-label="Tipo de item salvo">
          <button
            type="button"
            aria-pressed={tab === 'searches'}
            onClick={() => setTab('searches')}
          >
            Pesquisas {state.status === 'loaded' && <span>{searches.length}</span>}
          </button>
          <button
            type="button"
            aria-pressed={tab === 'decisions'}
            onClick={() => setTab('decisions')}
          >
            Decisões {bookmarks?.status === 'loaded' && <span>{bookmarks.items.length}</span>}
          </button>
        </div>
        {tab === 'decisions' ? (
          <>
            <p className="saved-items__intro">
              Reabra as decisões que você guardou para consultar depois.
            </p>
            <SavedDecisionsList />
          </>
        ) : (
          <>
            <p className="saved-items__intro">
              Reabra uma pesquisa com a mesma expressão, filtros e ordenação. Os resultados serão
              atualizados conforme a base atual.
            </p>
            {state.status === 'loading' && (
              <p role="status" className="saved-items__state">
                Carregando pesquisas salvas…
              </p>
            )}
            {state.status === 'failed' && (
              <div role="alert" className="saved-items__state">
                <p>{state.message}</p>
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
            {error && !error.id && (
              <p role="alert" className="saved-items__error">
                {error.message}
              </p>
            )}
            {state.status === 'loaded' && searches.length === 0 && (
              <div className="saved-items__empty">
                <h3>Sua primeira pesquisa salva começa aqui</h3>
                <p>
                  Faça uma busca, ajuste os filtros e clique em <strong>Salvar pesquisa</strong>{' '}
                  para dar um nome e retomar depois.
                </p>
                <button type="button" onClick={onClose}>
                  Voltar à pesquisa
                </button>
              </div>
            )}
            {searches.map((item) => (
              <article key={item.id} className="saved-items__card" aria-label={item.name}>
                <p className="saved-items__meta">
                  {String(item.filters.q).includes('"') ? 'Frase exata' : 'Termo livre'}
                  {Array.isArray(item.filters.tribunal) && item.filters.tribunal.length > 0
                    ? ` · ${item.filters.tribunal.join(', ')}`
                    : ''}
                </p>
                <h3>{item.name}</h3>
                {item.name.trim() !== String(item.filters.q).trim() && (
                  <p className="saved-items__expression">{String(item.filters.q)}</p>
                )}
                <p className="saved-items__date">
                  Salva em {formatDateTime(item.created_at)} · ordem:{' '}
                  {item.filters.order === 'date' ? 'mais recentes' : 'relevância'}
                </p>
                <div className="saved-items__card-actions">
                  <button
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => void run(item, 'resume')}
                  >
                    {busy?.id === item.id && busy.kind === 'resume' ? (
                      <>
                        <CircleNotch
                          className="saved-items__spinner"
                          size={14}
                          aria-hidden="true"
                        />{' '}
                        Reabrindo…
                      </>
                    ) : (
                      'Reabrir pesquisa'
                    )}
                  </button>
                  <button
                    type="button"
                    className="saved-items__remove"
                    disabled={Boolean(busy)}
                    aria-label={`Remover pesquisa ${item.name}`}
                    onClick={() => void run(item, 'delete')}
                  >
                    {busy?.id === item.id && busy.kind === 'delete' ? 'Removendo…' : 'Remover'}
                  </button>
                </div>
                {error?.id === item.id && (
                  <p role="alert" className="saved-items__error">
                    {error.message}
                  </p>
                )}
              </article>
            ))}
            <aside className="saved-items__notice">
              <Info size={17} aria-hidden="true" />
              <div>
                <strong>O recorte não congela a base</strong>
                <p>
                  Ao reabrir, expressão, filtros e ordenação são restaurados, mas novos documentos
                  podem alterar os resultados.
                </p>
              </div>
            </aside>
          </>
        )}
      </div>
    </dialog>,
    document.body,
  );
}
