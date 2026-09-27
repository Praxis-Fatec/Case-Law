import { useState } from 'react';
import { ArrowLeft, ArrowLineLeft, ArrowLineRight, ArrowRight } from '@phosphor-icons/react';

import {
  describePosition,
  lastPageOf,
  pageSlots,
  positionOf,
  type PageInfo,
} from '../search/paging';

type ResultsPaginationProps = {
  // The page the API answered. Null while a page is on its way: then nothing
  // is claimed about where the reader is.
  info: PageInfo | null;
  // The page asked for, to say what is loading.
  requestedPage: number;
  loading: boolean;
  onGo: (page: number) => void;
};

const number = new Intl.NumberFormat('pt-BR');

// Real buttons, disabled with the attribute and not only the look, so a
// keyboard or a screen reader meets them disabled too.
function ResultsPagination({ info, requestedPage, loading, onGo }: ResultsPaginationProps) {
  const position = info ? positionOf(info) : null;
  const busy = loading || position === null;

  // How many pages the result has, from the API's own total and page size.
  // While the next page loads the answer is gone, so the row keeps the count
  // it last read, disabled, rather than collapsing and growing back.
  const [knownLast, setKnownLast] = useState<number | null>(null);
  const fresh = info ? lastPageOf(info) : null;
  if (fresh !== null && fresh !== knownLast) {
    setKnownLast(fresh);
  }
  const last = fresh ?? knownLast;
  const current = info?.page ?? requestedPage;
  const slots = last === null ? [current] : pageSlots(Math.min(current, last), last);

  return (
    <nav className="results-pagination" aria-label="Páginas dos resultados">
      {/* Arrows for the four moves, each named for what it does, and the pages
          between them by number, so the keyboard and screen readers reach the
          same places as the pointer. */}
      <ul className="results-pagination__actions">
        <li>
          <button
            type="button"
            className="results-pagination__button results-pagination__button--edge"
            onClick={() => onGo(1)}
            disabled={busy || !position?.hasPrevious}
            aria-label="Primeira página"
            title="Primeira página"
          >
            <ArrowLineLeft size={13} aria-hidden="true" />
          </button>
        </li>
        <li>
          <button
            type="button"
            className="results-pagination__button"
            onClick={() => info && onGo(info.page - 1)}
            disabled={busy || !position?.hasPrevious}
            aria-label="Anterior"
            title="Página anterior"
          >
            <ArrowLeft size={13} aria-hidden="true" />
          </button>
        </li>

        {slots.map((slot) =>
          typeof slot === 'number' ? (
            <li key={slot}>
              <button
                type="button"
                className={
                  slot === current
                    ? 'results-pagination__page results-pagination__page--current'
                    : 'results-pagination__page'
                }
                onClick={() => slot !== current && onGo(slot)}
                disabled={busy && slot !== current}
                aria-current={slot === current ? 'page' : undefined}
                aria-label={`Página ${number.format(slot)}`}
              >
                {number.format(slot)}
              </button>
            </li>
          ) : (
            <li key={slot} className="results-pagination__gap" aria-hidden="true">
              …
            </li>
          ),
        )}

        <li>
          <button
            type="button"
            className="results-pagination__button"
            onClick={() => info && onGo(info.page + 1)}
            disabled={busy || !position?.hasNext}
            aria-label="Próxima"
            title="Próxima página"
          >
            <ArrowRight size={13} aria-hidden="true" />
          </button>
        </li>
        <li>
          <button
            type="button"
            className="results-pagination__button results-pagination__button--edge"
            onClick={() => last !== null && onGo(last)}
            disabled={busy || !position?.hasNext || last === null}
            aria-label="Última página"
            title="Última página"
          >
            <ArrowLineRight size={13} aria-hidden="true" />
          </button>
        </li>
      </ul>

      <p className="results-pagination__range" aria-live="polite">
        {loading || !position
          ? `Carregando a página ${requestedPage}...`
          : describePosition(position)}
      </p>
    </nav>
  );
}

export default ResultsPagination;
