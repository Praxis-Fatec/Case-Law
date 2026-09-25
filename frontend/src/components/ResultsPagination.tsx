import { CaretDoubleLeft, CaretLeft, CaretRight } from '@phosphor-icons/react';

import { describePosition, positionOf, type PageInfo } from '../search/paging';

type ResultsPaginationProps = {
  // The page the API answered. Null while a page is on its way: then nothing
  // is claimed about where the reader is.
  info: PageInfo | null;
  // The page asked for, to say what is loading.
  requestedPage: number;
  loading: boolean;
  onGo: (page: number) => void;
};

// Real buttons, disabled with the attribute and not only the look, so a
// keyboard or a screen reader meets them disabled too.
function ResultsPagination({ info, requestedPage, loading, onGo }: ResultsPaginationProps) {
  const position = info ? positionOf(info) : null;
  const busy = loading || position === null;

  return (
    <nav className="results-pagination" aria-label="Páginas dos resultados">
      <p className="results-pagination__range" aria-live="polite">
        {loading || !position
          ? `Carregando a página ${requestedPage}...`
          : describePosition(position)}
      </p>

      <div className="results-pagination__actions">
        <button
          type="button"
          className="results-pagination__button"
          onClick={() => onGo(1)}
          disabled={busy || !position?.hasPrevious}
        >
          <CaretDoubleLeft size={14} aria-hidden="true" />
          Primeira página
        </button>
        <button
          type="button"
          className="results-pagination__button"
          onClick={() => info && onGo(info.page - 1)}
          disabled={busy || !position?.hasPrevious}
        >
          <CaretLeft size={14} aria-hidden="true" />
          Anterior
        </button>
        <button
          type="button"
          className="results-pagination__button"
          onClick={() => info && onGo(info.page + 1)}
          disabled={busy || !position?.hasNext}
        >
          Próxima
          <CaretRight size={14} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

export default ResultsPagination;
