import { useEffect, useRef, useState } from 'react';
import { ArrowLeft } from '@phosphor-icons/react';

import { DecisionRequestError, getDecision, type Decision } from '../api/decisions';
import { formatDate, normalizeText } from './decisionFormat';

type DetailState =
  | { status: 'loading' }
  | { status: 'loaded'; decision: Decision }
  | { status: 'not-found' }
  | { status: 'failed' };

type DecisionDetailProps = {
  id: string;
  source: string;
  identifier: string;
  onClose: () => void;
};

type MetadataItem = { label: string; value: string };

// Only what the decision actually carries. An absent field is left out rather
// than shown with an empty value, so no label stands alone.
function metadataOf(decision: Decision): MetadataItem[] {
  const judged = formatDate(decision.judged_on);
  const published = formatDate(decision.published_on);

  const items: (MetadataItem | null)[] = [
    textItem('Número do processo', decision.case_number),
    textItem('Relator', decision.reporting_judge),
    textItem('Órgão julgador', decision.judging_body),
    decision.class_code !== null && Number.isFinite(decision.class_code)
      ? { label: 'Classe processual (código CNJ)', value: String(decision.class_code) }
      : null,
    judged ? { label: 'Data do julgamento', value: judged } : null,
    published ? { label: 'Data da publicação', value: published } : null,
  ];

  // Neither date on its own: the reference date the API always sends, named for
  // what it is rather than passed off as one of the two.
  if (!judged && !published) {
    const decided = formatDate(decision.decided_on);
    items.push(decided ? { label: 'Data da decisão', value: decided } : null);
  }

  return items.filter((item): item is MetadataItem => item !== null);
}

function textItem(label: string, value: string | null): MetadataItem | null {
  const normalized = normalizeText(value);
  return normalized ? { label, value: normalized } : null;
}

function DecisionDetail({ id, source, identifier, onClose }: DecisionDetailProps) {
  const [state, setState] = useState<DetailState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    // Opening another decision remounts this panel; a retry runs this again.
    // Either way the request in flight is abandoned, so a late answer never
    // replaces the one on screen.
    const controller = new AbortController();
    let active = true;

    getDecision(source, identifier, { signal: controller.signal }).then(
      (decision) => {
        if (active) {
          setState({ status: 'loaded', decision });
        }
      },
      (error: unknown) => {
        if (!active) {
          return;
        }
        const missing = error instanceof DecisionRequestError && error.status === 404;
        setState({ status: missing ? 'not-found' : 'failed' });
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [source, identifier, attempt]);

  // Where a keyboard or screen reader user lands once the decision is there.
  useEffect(() => {
    if (state.status === 'loaded') {
      titleRef.current?.focus();
    }
  }, [state.status]);

  const retry = () => {
    setState({ status: 'loading' });
    setAttempt((current) => current + 1);
  };

  const titleId = `${id}-title`;

  return (
    <aside
      id={id}
      className="decision-detail"
      aria-labelledby={titleId}
      aria-busy={state.status === 'loading'}
    >
      <div className="decision-detail__toolbar">
        <button type="button" className="decision-detail__back" onClick={onClose}>
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar aos resultados
        </button>
      </div>

      {state.status === 'loading' && (
        <>
          <h2 id={titleId} className="sr-only">
            Decisão
          </h2>
          <p className="search-state search-state--loading" role="status">
            Carregando decisão...
          </p>
        </>
      )}

      {state.status === 'not-found' && (
        <div className="search-state search-state--error" role="alert">
          <h2 id={titleId} className="decision-detail__state-title">
            Decisão não encontrada
          </h2>
          <p>
            Ela não está mais disponível na base. Decisões sob segredo de justiça também não são
            exibidas.
          </p>
        </div>
      )}

      {state.status === 'failed' && (
        <div className="search-state search-state--error" role="alert">
          <h2 id={titleId} className="decision-detail__state-title">
            Não foi possível carregar a decisão
          </h2>
          <p>Verifique a conexão e tente novamente.</p>
          <button type="button" className="search-state__retry" onClick={retry}>
            Tentar novamente
          </button>
        </div>
      )}

      {state.status === 'loaded' && (
        <DecisionContent decision={state.decision} titleId={titleId} titleRef={titleRef} />
      )}
    </aside>
  );
}

type DecisionContentProps = {
  decision: Decision;
  titleId: string;
  titleRef: React.RefObject<HTMLHeadingElement>;
};

function DecisionContent({ decision, titleId, titleRef }: DecisionContentProps) {
  const metadata = metadataOf(decision);
  const court = normalizeText(decision.court);
  const caseNumber = normalizeText(decision.case_number);

  return (
    <>
      <header className="decision-detail__header">
        {court && <span className="decision-detail__court">{court}</span>}
        <h2 id={titleId} ref={titleRef} tabIndex={-1} className="decision-detail__title">
          {caseNumber ? `Processo ${caseNumber}` : 'Decisão sem número de processo informado'}
        </h2>
      </header>

      {metadata.length > 0 && (
        <dl className="decision-detail__meta">
          {metadata.map((item) => (
            <div className="decision-detail__meta-item" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* The whole ementa, as the court wrote it — never the search snippet.
          Read without a search term, so it is plain text and rendered as text. */}
      <section className="decision-detail__reading" aria-labelledby={`${titleId}-ementa`}>
        <h3 id={`${titleId}-ementa`} className="decision-detail__section-title">
          Ementa
        </h3>
        <p className="decision-detail__summary">{decision.summary}</p>
      </section>
    </>
  );
}

export default DecisionDetail;
