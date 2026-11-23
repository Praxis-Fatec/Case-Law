import { useState } from 'react';
import { BookmarkSimple, CircleNotch } from '@phosphor-icons/react';
import { bookmarkFailure, bookmarkKey, type DecisionKey } from '../api/savedDecisions';
import { useSavedDecisions } from '../search/savedDecisionsContext';

export default function SaveDecisionButton({ source, identifier }: DecisionKey) {
  const bookmarks = useSavedDecisions();
  const [error, setError] = useState('');
  if (!bookmarks) return null;
  const key = { source, identifier };
  const saved = bookmarks.items.some((item) => bookmarkKey(item) === bookmarkKey(key));
  const busy = bookmarks.pending.has(bookmarkKey(key));
  return (
    <span className="save-decision">
      <button
        type="button"
        className={`save-decision__button${saved ? ' save-decision__button--saved' : ''}`}
        aria-label={
          bookmarks.status === 'failed'
            ? 'Tentar carregar itens salvos'
            : saved
              ? 'Remover decisão dos itens salvos'
              : 'Salvar decisão'
        }
        aria-pressed={saved}
        disabled={busy || bookmarks.status === 'loading'}
        onClick={() => {
          setError('');
          if (bookmarks.status === 'failed') {
            bookmarks.retry();
            return;
          }
          void bookmarks.toggle(key).catch((failure) => setError(bookmarkFailure(failure)));
        }}
      >
        {busy ? (
          <CircleNotch size={16} className="saved-items__spinner" aria-hidden="true" />
        ) : (
          <BookmarkSimple size={16} weight={saved ? 'fill' : 'regular'} aria-hidden="true" />
        )}
        {bookmarks.status === 'failed'
          ? 'Tentar carregar itens salvos'
          : busy
            ? 'Atualizando…'
            : saved
              ? 'Salvo'
              : 'Salvar'}
      </button>
      {(error || bookmarks.status === 'failed') && (
        <span role="alert" className="saved-items__error">
          {error || bookmarks.error}
        </span>
      )}
    </span>
  );
}
