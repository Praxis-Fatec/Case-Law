import { lazy, Suspense } from 'react';
import type { VolumeByPeriod } from '../api/indicators';

const TimelineChart = lazy(() => import('./TimelineChart'));

export type TimelineState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed' }
  | { status: 'loaded'; volume: VolumeByPeriod };

export default function TimelineVolumePanel({
  timeline,
  onRetry,
}: {
  timeline: TimelineState;
  onRetry: () => void;
}) {
  const volume = timeline.status === 'loaded' ? timeline.volume : null;
  const loading = timeline.status === 'loading';
  const empty = volume && (volume.total === 0 || volume.periods.length === 0);
  return (
    <section className="panorama temporal-volume" aria-labelledby="timeline-panel-title">
      <header className="panorama__header">
        <div>
          <p className="panorama__eyebrow">Movimento no período</p>
          <h2 id="timeline-panel-title" className="panorama__title">
            Evolução do volume de decisões
          </h2>
        </div>
        <p className="panorama__lead">
          Passe o cursor sobre um período para consultar a quantidade de decisões.
        </p>
      </header>
      <article
        className="panorama-card temporal-volume__card"
        aria-label="Volume ao longo do tempo"
        aria-busy={loading}
      >
        <div className="panorama-card__body">
          {timeline.status === 'idle' && (
            <p className="panorama-card__message">
              Pesquise um tema para ver a evolução do volume de decisões.
            </p>
          )}
          {loading && (
            <p className="panorama-card__message" role="status">
              Carregando o volume ao longo do tempo...
            </p>
          )}
          {timeline.status === 'failed' && (
            <div className="search-state search-state--error panorama-card__error" role="alert">
              <p>Não foi possível carregar o volume ao longo do tempo.</p>
              <button
                type="button"
                className="search-state__retry"
                aria-label="Tentar novamente o gráfico temporal"
                onClick={onRetry}
              >
                Tentar novamente
              </button>
            </div>
          )}
          {empty && (
            <p className="panorama-card__message">
              Nenhum dado temporal encontrado para os filtros aplicados. Revise os termos ou amplie
              o período.
            </p>
          )}
          {volume && !empty && (
            <Suspense fallback={<p role="status">Carregando gráfico temporal...</p>}>
              <TimelineChart
                periods={volume.periods}
                granularity={volume.granularity}
                showValues={false}
                height={330}
              />
            </Suspense>
          )}
        </div>
      </article>
    </section>
  );
}
