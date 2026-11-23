import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BookmarkSimple, CircleNotch, X } from '@phosphor-icons/react';
import {
  createSavedSearch,
  savedSearchFailure,
  type SavedSearch,
  type SavedSearchParams,
} from '../api/savedSearches';
import { useDialog } from './useDialog';

function SaveDialog({
  params,
  onClose,
  onSaved,
  returnFocusId,
}: {
  params: SavedSearchParams;
  onClose: () => void;
  onSaved: (search: SavedSearch) => void;
  returnFocusId: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  useDialog(dialog, returnFocusId);
  useEffect(() => () => request.current?.abort(), []);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (request.current) return;
    if (!name.trim()) {
      setError('Informe um nome para a pesquisa.');
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setSaving(true);
    setError(null);
    try {
      const search = await createSavedSearch(name.trim(), params, controller.signal);
      if (!controller.signal.aborted) onSaved(search);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(savedSearchFailure(failure));
        setSaving(false);
        request.current = null;
      }
    }
  };
  return createPortal(
    <dialog
      ref={dialog}
      className="save-search-dialog"
      aria-labelledby="save-search-title"
      aria-describedby="save-search-context"
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <header>
        <p className="saved-items__eyebrow">Memória de trabalho</p>
        <h2 id="save-search-title">Salvar pesquisa</h2>
        <button
          type="button"
          className="saved-items__close"
          aria-label="Fechar salvar pesquisa"
          onClick={onClose}
        >
          <X size={20} aria-hidden="true" />
        </button>
        <p id="save-search-context">
          Salve a expressão, os filtros aplicados e a ordenação para retomar depois.
        </p>
      </header>
      <p className="save-search-dialog__expression">“{params.q}”</p>
      <form onSubmit={submit}>
        <label htmlFor={nameId}>Nome da pesquisa</label>
        <input
          id={nameId}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={120}
          autoFocus
          disabled={saving}
          placeholder="Ex.: Prescrição em execução fiscal"
          aria-invalid={Boolean(error)}
        />
        {error && (
          <p role="alert" className="saved-items__error">
            {error}
          </p>
        )}
        <div className="save-search-dialog__actions">
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="save-search-dialog__submit" disabled={saving}>
            {saving && (
              <CircleNotch className="saved-items__spinner" size={16} aria-hidden="true" />
            )}
            {saving ? 'Salvando…' : 'Salvar pesquisa'}
          </button>
        </div>
      </form>
    </dialog>,
    document.body,
  );
}

export default function SaveSearchAction({
  params,
  disabled,
  removedSearchId,
  onSaved,
}: {
  params: SavedSearchParams;
  disabled: boolean;
  removedSearchId: string | null;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const saved = savedId !== null && savedId !== removedSearchId;
  const trigger = useId();
  const hintId = useId();
  return (
    <div className="save-search-action">
      <button
        id={trigger}
        type="button"
        className={`save-search-action__button${saved ? ' save-search-action__button--saved' : ''}`}
        disabled={disabled}
        aria-disabled={disabled || saved}
        aria-label={saved ? 'Pesquisa salva' : 'Salvar pesquisa'}
        aria-describedby={hintId}
        aria-haspopup={saved ? undefined : 'dialog'}
        onClick={() => {
          if (!saved) setOpen(true);
        }}
      >
        <BookmarkSimple size={18} weight={saved ? 'fill' : 'regular'} aria-hidden="true" />
        <span>
          <strong>{saved ? 'Pesquisa salva' : 'Salvar pesquisa'}</strong>
          <small id={hintId}>
            {saved ? 'Disponível em Itens salvos' : 'Retomar depois com os mesmos filtros'}
          </small>
        </span>
      </button>
      <span className="sr-only" aria-live="polite">
        {saved ? 'Pesquisa salva. Disponível em Itens salvos.' : ''}
      </span>
      {open && (
        <SaveDialog
          params={params}
          returnFocusId={trigger}
          onClose={() => setOpen(false)}
          onSaved={(search) => {
            setSavedId(search.id);
            setOpen(false);
            onSaved();
          }}
        />
      )}
    </div>
  );
}
