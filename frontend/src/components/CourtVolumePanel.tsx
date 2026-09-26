import { Info } from '@phosphor-icons/react';

import CourtVolumeChart from './CourtVolumeChart';
import { formatCount, formatDateTime, NOT_INFORMED, UNAVAILABLE } from './coverageFormat';
import type { LastUpdateState, VolumeState } from './volumeFormat';

const plural = (count: number, one: string, many: string) =>
  `${formatCount(count)} ${count === 1 ? one : many}`;

// What stands in place of the chart and of the list while there is nothing to
// draw. Each state says what it is: no search yet, on its way, not available,
// or a cut that matched nothing — never an empty frame.
function messages(state: VolumeState): { chart: string; list: string } | null {
  switch (state.status) {
    case 'idle':
      return {
        chart: 'Pesquise um tema para ver em quais tribunais ele aparece.',
        list: 'A composição aparece depois de uma pesquisa.',
      };
    case 'unavailable':
      return {
        chart: 'O volume por tribunal está indisponível no momento.',
        list: 'A composição do recorte está indisponível no momento.',
      };
    case 'loaded':
      if (state.volume.total === 0 || state.volume.courts.length === 0) {
        return state.volume.total === 0
          ? {
              chart: 'Nenhuma decisão atende ao recorte aplicado. Não há volume para mostrar.',
              list: 'Nenhum tribunal no recorte.',
            }
          : {
              chart: 'O volume por tribunal não foi informado.',
              list: 'A composição do recorte não foi informada.',
            };
      }
      return null;
    default:
      return null;
  }
}

// The collection's date, the same for every court. Without a finished load
// the reason is said rather than a missing value.
function lastUpdateText(state: LastUpdateState): { text: string; known: boolean } | null {
  if (state.status === 'loading') {
    return null;
  }
  if (state.status === 'unavailable') {
    return { text: UNAVAILABLE, known: false };
  }
  const updated = formatDateTime(state.lastUpdate.updated_at);
  if (updated) {
    return { text: updated, known: true };
  }
  const neverFinished =
    state.lastUpdate.state === 'all_loads_failed' || state.lastUpdate.state === 'never_loaded';
  return { text: neverFinished ? 'Nenhuma coleta concluída' : NOT_INFORMED, known: false };
}

function ChartSkeleton() {
  return (
    <div className="volume-skeleton">
      {['82%', '58%', '34%'].map((width) => (
        <span key={width} className="volume-skeleton__bar" style={{ width }} />
      ))}
      <span className="sr-only">Carregando o volume por tribunal</span>
    </div>
  );
}

type CourtVolumePanelProps = {
  volume: VolumeState;
  lastUpdate: LastUpdateState;
};

function CourtVolumePanel({ volume, lastUpdate }: CourtVolumePanelProps) {
  const loading = volume.status === 'loading';
  const message = messages(volume);
  const loaded = volume.status === 'loaded' && !message ? volume.volume : null;
  const total = volume.status === 'loaded' ? volume.volume.total : null;
  const updated = lastUpdateText(lastUpdate);

  return (
    <section className="panorama" aria-labelledby="panorama-title">
      <header className="panorama__header">
        <div>
          <p className="panorama__eyebrow">Indicador explicável · Sprint 1</p>
          <h2 id="panorama-title" className="panorama__title">
            Onde o tema aparece com mais frequência?
          </h2>
        </div>
        <p className="panorama__lead">
          O volume usa os mesmos termos, tribunais e períodos da lista.
        </p>
      </header>

      <div className="panorama__grid">
        <article className="panorama-card" aria-labelledby="volume-title" aria-busy={loading}>
          <header className="panorama-card__header">
            <h3 id="volume-title" className="panorama-card__title">
              Volume por tribunal
            </h3>
            {total !== null && (
              <p className="panorama-card__meta">
                {plural(total, 'decisão no recorte', 'decisões no recorte')}
              </p>
            )}
          </header>

          <div className="panorama-card__body">
            {loading && <ChartSkeleton />}
            {message && <p className="panorama-card__message">{message.chart}</p>}
            {loaded && <CourtVolumeChart courts={loaded.courts} />}
          </div>

          <footer className="volume-card__footer">
            <p className="volume-card__note">
              <Info size={13} aria-hidden="true" />
              Frequência não representa relevância jurídica.
            </p>
            <p className="volume-card__updated">
              Última atualização da base:{' '}
              {updated === null ? (
                <span className="volume-card__updated-pending">
                  <span className="sr-only">Carregando</span>
                </span>
              ) : (
                <strong className={updated.known ? undefined : 'is-missing'}>{updated.text}</strong>
              )}
            </p>
          </footer>
        </article>

        <article
          className="panorama-card panorama-card--composition"
          aria-labelledby="composition-title"
          aria-busy={loading}
        >
          <header className="panorama-card__header">
            <h3 id="composition-title" className="panorama-card__title">
              Composição do recorte
            </h3>
            {total !== null && (
              <p className="panorama-card__meta">{plural(total, 'documento', 'documentos')}</p>
            )}
          </header>

          {loading && (
            <ul className="composition__list" aria-hidden="true">
              {[1, 2, 3].map((n) => (
                <li key={n} className="composition__item composition__item--pending">
                  <span className="volume-skeleton__line" />
                </li>
              ))}
            </ul>
          )}

          {message && <p className="panorama-card__message">{message.list}</p>}

          {/* The same answer the chart is drawn from, in the order it came. */}
          {loaded && (
            <ol className="composition__list">
              {loaded.courts.map((court, index) => (
                <li key={court.abbreviation} className="composition__item">
                  <span className="composition__rank" aria-hidden="true">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="composition__court">
                    <strong className="composition__abbreviation">{court.abbreviation}</strong>
                    {court.name && <span className="composition__name">{court.name}</span>}
                  </span>
                  {court.decisions === null ? (
                    <span className="composition__count is-missing">{NOT_INFORMED}</span>
                  ) : (
                    <span className="composition__count">
                      {formatCount(court.decisions)}
                      <span className="sr-only">
                        {court.decisions === 1 ? ' decisão' : ' decisões'}
                      </span>
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}

          {/* The rule the endpoint applies, and only that: a count in the
              database of the decisions the search's own narrowing matches.
              Decisions under seal never enter the base. */}
          <div className="composition__explain">
            <h4 className="composition__explain-title">Como este número é formado?</h4>
            <p className="composition__explain-text">
              Contagem de decisões públicas únicas que atendem ao recorte, agrupadas por tribunal.
              Decisões em segredo de justiça não entram na base e não integram o cálculo.
            </p>
          </div>
        </article>
      </div>
    </section>
  );
}

export default CourtVolumePanel;
