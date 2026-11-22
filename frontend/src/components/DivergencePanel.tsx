import { Info, WarningCircle } from '@phosphor-icons/react';
import type {
  DivergenceCounts,
  DivergencePair,
  DivergencePanelNumbers,
  DivergenceSample,
} from '../api/divergence';
import { DIVERGENCE_REASONS, type DivergenceState } from './divergenceFormat';
import { formatCount } from './coverageFormat';
import { percent } from './outcomeFormat';

const outcomes: [keyof DivergenceCounts, string][] = [
  ['denied', 'Negado'],
  ['granted', 'Provido'],
  ['partially_granted', 'Parcialmente provido'],
];
const pValue = (value: number) =>
  value === 0
    ? '< 1e-300'
    : value < 0.001
      ? value.toExponential(2)
      : value.toLocaleString('pt-BR', { maximumSignificantDigits: 4 });

function PanelCard({ panel, minimum }: { panel: DivergencePanelNumbers; minimum: number }) {
  return (
    <article
      className="divergence__panel"
      aria-label={`${panel.panel ?? 'Órgão não informado'} — ${panel.court}`}
    >
      <h4>{panel.panel ?? 'Órgão julgador não informado'}</h4>
      <p className="divergence__count">
        <strong>{formatCount(panel.documents)}</strong> decisões no recorte
      </p>
      <p>
        {formatCount(panel.processes)} processos identificados, antes das exclusões de cada par.
      </p>
      <dl className="divergence__numbers">
        {outcomes.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{formatCount(panel.outcomes[key])}</dd>
          </div>
        ))}
        <div>
          <dt>Resultado não classificado</dt>
          <dd>{formatCount(panel.unknown_documents)}</dd>
        </div>
      </dl>
      <p className="divergence__muted">
        Os resultados acima contam documentos, não a amostra estatística.
      </p>
      {panel.processes < minimum && (
        <p className="divergence__insufficient">
          Volume insuficiente: menos de {minimum} processos identificados; sem conclusão
          estatística.
        </p>
      )}
      {(panel.missing_process_documents > 0 || panel.repeated_documents > 0) && (
        <p className="divergence__muted">
          {formatCount(panel.missing_process_documents)} documentos sem processo identificado ·{' '}
          {formatCount(panel.repeated_documents)} documentos repetidos em processos.
        </p>
      )}
    </article>
  );
}

function SampleNumbers({ sample }: { sample: DivergenceSample }) {
  return (
    <div className="divergence__sample">
      <h5>{sample.panel}</h5>
      <p>
        <strong>{formatCount(sample.classified)}</strong> processos classificados de{' '}
        {formatCount(sample.processes)} na amostra
      </p>
      <p>
        Cobertura: {sample.coverage === null ? 'Não informada' : percent(sample.coverage * 100)} ·{' '}
        {formatCount(sample.unknown)} sem classificação
      </p>
      <dl className="divergence__numbers">
        {outcomes.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>
              {formatCount(sample.outcomes[key])} ·{' '}
              {sample.classified
                ? percent((sample.outcomes[key] / sample.classified) * 100)
                : 'Percentual indisponível'}
            </dd>
          </div>
        ))}
      </dl>
      <p className="divergence__muted">
        Excluídos: {formatCount(sample.shared_processes_excluded)} processos compartilhados pelo
        par; {formatCount(sample.missing_process_documents)} documentos sem processo;{' '}
        {formatCount(sample.repeated_documents)} documentos repetidos.
      </p>
    </div>
  );
}

function Pair({ pair }: { pair: DivergencePair }) {
  const highlighted = pair.signal && pair.reason === 'difference';
  return (
    <details
      className={`divergence__pair${highlighted ? ' divergence__pair--signal' : ''}`}
      open={highlighted}
    >
      <summary>
        <span>
          {pair.left.panel} × {pair.right.panel}
        </span>
        <span className="divergence__reason">
          {highlighted && <WarningCircle size={16} aria-hidden="true" />}
          {!pair.signal && pair.reason === 'difference'
            ? 'Sem sinal estatístico confirmado.'
            : (DIVERGENCE_REASONS[pair.reason] ??
              'Sem conclusão: motivo não informado pela análise.')}
        </span>
        <span className="divergence__muted">
          {formatCount(pair.left.classified)} × {formatCount(pair.right.classified)} processos
          classificados · detalhes da comparação
        </span>
      </summary>
      <div className="divergence__samples">
        <SampleNumbers sample={pair.left} />
        <SampleNumbers sample={pair.right} />
      </div>
      {pair.adjusted_p !== null && (
        <p className="divergence__test">
          p ajustado (Holm): {pValue(pair.adjusted_p)}
          {pair.effect !== null &&
            ` · Maior diferença: ${(pair.effect * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} pontos percentuais`}
        </p>
      )}
    </details>
  );
}

export default function DivergencePanel({
  divergence: state,
  onRetry,
}: {
  divergence: DivergenceState;
  onRetry: () => void;
}) {
  const data = state.status === 'loaded' ? state.divergence : null;
  const groups = new Map<
    string,
    { court: string; classCode: number | null; panels: DivergencePanelNumbers[] }
  >();
  for (const panel of data?.panels ?? []) {
    const key = JSON.stringify([panel.court, panel.class_code]);
    const group = groups.get(key) ?? {
      court: panel.court,
      classCode: panel.class_code,
      panels: [],
    };
    group.panels.push(panel);
    groups.set(key, group);
  }
  return (
    <section
      className="panorama divergence"
      aria-labelledby="divergence-title"
      aria-busy={state.status === 'loading'}
    >
      <header className="panorama-card__header">
        <div>
          <p className="panorama__eyebrow">Comparação dentro do mesmo tribunal</p>
          <h3 id="divergence-title" className="panorama-card__title">
            Como as turmas decidiram o tema
          </h3>
        </div>
      </header>
      <p className="panorama__lead">
        Mesma pesquisa e filtros. A comparação separa tribunais e classes processuais e mantém
        visíveis as amostras insuficientes.
      </p>
      {state.status === 'idle' && (
        <p>Pesquise um tema para comparar os resultados das turmas do mesmo tribunal.</p>
      )}
      {state.status === 'loading' && <p role="status">Carregando os resultados por turma…</p>}
      {state.status === 'failed' && (
        <div role="alert" className="divergence__error">
          <p>{state.message}</p>
          <button type="button" onClick={onRetry}>
            Tentar novamente
          </button>
        </div>
      )}
      {data?.documents === 0 && (
        <p>
          Nenhuma decisão encontrada para os filtros aplicados. Ajuste os termos ou amplie o
          período.
        </p>
      )}
      {data && data.documents > 0 && (
        <>
          <p className="divergence__method">
            {formatCount(data.documents)} decisões · {data.rule_version} · mínimo de{' '}
            {data.thresholds.minimum_classified_processes} processos distintos classificados por
            turma e {percent(data.thresholds.minimum_classification_coverage * 100)} de cobertura.
            Sinal exige p ajustado ≤ {data.thresholds.alpha.toLocaleString('pt-BR')} e diferença ≥{' '}
            {(data.thresholds.minimum_effect * 100).toLocaleString('pt-BR')} pontos percentuais.
          </p>
          {[...groups.entries()].map(([key, group]) => {
            const pairs = data.pairs.filter(
              (pair) => pair.court === group.court && pair.class_code === group.classCode,
            );
            return (
              <section
                className="divergence__group"
                key={key}
                aria-label={`${group.court} — ${group.classCode === null ? 'Classe não informada' : `Classe CNJ ${group.classCode}`}`}
              >
                <h4 className="divergence__group-title">
                  {group.court} ·{' '}
                  {group.classCode === null
                    ? 'Classe processual não informada'
                    : `Classe CNJ ${group.classCode}`}
                </h4>
                <div className="divergence__panels">
                  {group.panels.map((panel) => (
                    <PanelCard
                      key={panel.panel ?? 'missing'}
                      panel={panel}
                      minimum={data.thresholds.minimum_classified_processes}
                    />
                  ))}
                </div>
                {pairs.length ? (
                  <div className="divergence__pairs">
                    {pairs.map((pair) => (
                      <Pair key={JSON.stringify([pair.left.panel, pair.right.panel])} pair={pair} />
                    ))}
                  </div>
                ) : (
                  <p className="divergence__muted">
                    Sem conclusão: não há duas turmas com tribunal e classe identificados neste
                    grupo.
                  </p>
                )}
              </section>
            );
          })}
        </>
      )}
      <aside className="divergence__notice">
        <Info size={17} aria-hidden="true" />
        <p>
          Diferença estatística não comprova divergência jurídica nem prevê o resultado de um
          processo. A classificação é automática; confira as decisões e a competência das turmas.
        </p>
      </aside>
    </section>
  );
}
