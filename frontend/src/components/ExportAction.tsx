import { useEffect, useId, useRef, useState } from 'react';
import { DownloadSimple } from '@phosphor-icons/react';
import {
  downloadPdf,
  exportPdf,
  getExportLimit,
  ExportRequestError,
  type ExportParams,
} from '../api/exports';

type ExportState =
  { status: 'ready' | 'generating' | 'complete' } | { status: 'failed'; message: string };

export default function ExportAction({
  params,
  total,
  disabled,
}: {
  params: ExportParams;
  total: number | null;
  disabled: boolean;
}) {
  const [limit, setLimit] = useState<number | null>(null);
  const hintId = useId();
  const [limitFailed, setLimitFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ExportState>({ status: 'ready' });
  const inFlight = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getExportLimit(controller.signal).then(
      (value) => {
        if (!controller.signal.aborted) {
          setLimit(value);
          setLimitFailed(false);
        }
      },
      () => {
        if (!controller.signal.aborted) setLimitFailed(true);
      },
    );
    return () => {
      controller.abort();
      inFlight.current?.abort();
    };
  }, [attempt]);

  const generate = async () => {
    if (inFlight.current || disabled || !total || limit === null || total > limit) return;
    const controller = new AbortController();
    inFlight.current = controller;
    setState({ status: 'generating' });
    try {
      const result = await exportPdf(params, controller.signal);
      if (controller.signal.aborted) return;
      downloadPdf(result.blob, result.filename);
      setState({ status: 'complete' });
    } catch (error) {
      if (!controller.signal.aborted)
        setState({
          status: 'failed',
          message:
            error instanceof ExportRequestError
              ? error.message
              : 'Não foi possível exportar o recorte. Tente novamente.',
        });
    } finally {
      if (inFlight.current === controller) inFlight.current = null;
    }
  };
  const blocked = disabled || total === null || total === 0 || limit === null || total > limit;
  const count = total?.toLocaleString('pt-BR');
  const hint =
    total === 0
      ? 'Não há decisões neste recorte para exportar.'
      : limitFailed
        ? 'Não foi possível consultar o limite de exportação.'
        : limit === null
          ? 'Consultando limite de exportação...'
          : total !== null && total > limit
            ? `O recorte tem ${count} decisões. O limite é ${limit.toLocaleString('pt-BR')}. Aplique mais filtros para exportar.`
            : `Limite: ${limit.toLocaleString('pt-BR')} decisões por exportação.`;
  return (
    <div className="export-action" aria-label="Exportação do recorte">
      <button
        type="button"
        className="export-action__button"
        onClick={generate}
        aria-describedby={hintId}
        disabled={blocked || state.status === 'generating'}
      >
        <DownloadSimple size={16} aria-hidden="true" />
        {state.status === 'generating'
          ? 'Gerando PDF...'
          : state.status === 'failed'
            ? 'Tentar exportar novamente'
            : `Exportar recorte${total !== null ? ` · ${count} ${total === 1 ? 'decisão' : 'decisões'}` : ''}`}
      </button>
      <p id={hintId} className="export-action__hint">
        {hint}
      </p>
      {limitFailed && (
        <button
          type="button"
          className="search-state__retry"
          onClick={() => setAttempt((value) => value + 1)}
        >
          Tentar carregar limite de exportação
        </button>
      )}
      {state.status === 'generating' && (
        <p role="status">Gerando o PDF do recorte. Aguarde a conclusão.</p>
      )}
      {state.status === 'complete' && <p role="status">PDF gerado e enviado para download.</p>}
      {state.status === 'failed' && <p role="alert">{state.message}</p>}
    </div>
  );
}
