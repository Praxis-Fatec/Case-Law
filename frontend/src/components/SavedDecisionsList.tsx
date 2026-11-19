import { useState } from 'react';
import { Link } from 'react-router-dom';
import { bookmarkFailure, bookmarkKey } from '../api/savedDecisions';
import { useSavedDecisions } from '../search/savedDecisionsContext';
import { formatDateTime } from './coverageFormat';

export default function SavedDecisionsList() {
  const bookmarks = useSavedDecisions();
  const [error, setError] = useState<{ key: string; message: string } | null>(null);
  if (!bookmarks) return null;
  if (bookmarks.status === 'loading')
    return (
      <p role="status" className="saved-items__state">
        Carregando decisões salvas…
      </p>
    );
  if (bookmarks.status === 'failed')
    return (
      <div role="alert" className="saved-items__state">
        <p>{bookmarks.error}</p>
        <button type="button" onClick={bookmarks.retry}>
          Tentar novamente
        </button>
      </div>
    );
  if (!bookmarks.items.length)
    return (
      <div className="saved-items__empty">
        <h3>Guarde sua primeira decisão</h3>
        <p>
          Nos resultados ou no detalhe de uma decisão, clique em <strong>Salvar</strong> para
          encontrá-la aqui depois.
        </p>
      </div>
    );
  return (
    <>
      {bookmarks.items.map((item) => {
        const id = bookmarkKey(item);
        const busy = bookmarks.pending.has(id);
        return (
          <article
            key={id}
            className="saved-items__card"
            aria-label={`Decisão ${item.case_number ?? item.identifier}`}
          >
            <p className="saved-items__meta">{item.court}</p>
            <h3>
              {item.case_number
                ? `Processo ${item.case_number}`
                : 'Decisão sem número de processo informado'}
            </h3>
            <p className="saved-items__expression saved-decision__summary">{item.summary}</p>
            <p className="saved-items__date">Salva em {formatDateTime(item.created_at)}</p>
            {!item.available && (
              <p className="saved-items__error">
                Esta decisão não está mais disponível no acervo. O item salvo foi preservado para
                sua referência.
              </p>
            )}
            <div className="saved-items__card-actions">
              {item.available && (
                <Link
                  className="saved-decision__open"
                  to={`/decisoes/${encodeURIComponent(item.source)}/${encodeURIComponent(item.identifier)}`}
                  replace
                >
                  Abrir decisão
                </Link>
              )}
              <button
                type="button"
                className="saved-items__remove"
                disabled={busy}
                aria-label={`Remover decisão ${item.case_number ?? item.identifier}`}
                onClick={() => {
                  setError(null);
                  void bookmarks
                    .toggle(item)
                    .catch((failure) => setError({ key: id, message: bookmarkFailure(failure) }));
                }}
              >
                {busy ? 'Removendo…' : 'Remover'}
              </button>
            </div>
            {error?.key === id && (
              <p role="alert" className="saved-items__error">
                {error.message}
              </p>
            )}
          </article>
        );
      })}
    </>
  );
}
