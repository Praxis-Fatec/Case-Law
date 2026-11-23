import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, WarningCircle } from '@phosphor-icons/react';

import { getRelatedDecisions, type Neighbour, type Relation } from '../api/related';
import { detailPath } from './decisionAddress';
import { formatDate, normalizeText } from './decisionFormat';
import { spell } from './stems';

/**
 * Other decisions in the base that treat the same subject as this one.
 *
 * Nobody related them: the base did, by weighing every word of the ementa by
 * how rare it is in judicial language and comparing what is left. `RF20`
 * requires that to be said — the method stated, and a computed relation told
 * apart from an official one — so the method comes from the answer and the
 * line under the heading says it before the first card.
 *
 * It also says the thing the requirement is careful about: proximity is not
 * agreement. These decisions are about the same subject, and one of them may
 * have decided it the other way.
 *
 * Placed right after the precedents on purpose. Those are the relations the
 * court itself made; these are ours. Side by side, the difference is visible
 * rather than merely written.
 *
 * It fetches on its own, and nothing here can keep the decision from being
 * read: a failure becomes a line inside this block and stops there.
 */

type RelatedDecisionsProps = {
  source: string;
  identifier: string;
  // The ementa on screen, which is where the matched stems are spelled from.
  ementa: string;
  headingId: string;
};

type State =
  { status: 'loading' } | { status: 'loaded'; relation: Relation } | { status: 'failed' };

const LIMIT = 5;

// A decision's rare terms are single words — shorter than a catalogued subject
// — so four of them still fit beside the label at a glance.
const MAX_SHARED_TERMS = 4;

// Said when the answer does not say, which only happens against an API older
// than this screen. Never guessed into something stronger: an unstated method
// is not an official relation.
const FALLBACK_METHOD = 'similaridade calculada';

function Close({
  neighbour,
  ementa,
  search,
}: {
  neighbour: Neighbour;
  ementa: string;
  search: string;
}) {
  const caseNumber = normalizeText(neighbour.case_number);
  const decided = formatDate(neighbour.decided_on);
  const byline = [normalizeText(neighbour.court), normalizeText(neighbour.judging_body), decided]
    .filter(Boolean)
    .join(' · ');
  const shared = spell(ementa, neighbour.matched_on, MAX_SHARED_TERMS);
  const name = caseNumber ? `Processo ${caseNumber}` : 'Decisão sem número de processo informado';

  return (
    <article className="neighbour" aria-label={name}>
      <h4 className="neighbour__case">
        {/* Pushed, not replaced: a suggestion is a trail, and Back should
            retrace it to the decision it was followed from. The search travels
            with the address so the list is still the list on the way back. */}
        <Link className="neighbour__link" to={{ pathname: detailPath(neighbour), search }}>
          {name}
          <ArrowRight size={14} weight="bold" aria-hidden="true" />
        </Link>
      </h4>

      {byline && <p className="neighbour__byline">{byline}</p>}

      {shared.length > 0 && (
        <p className="neighbour__ground">
          <span className="neighbour__ground-label">Termos em comum:</span> {shared.join(' · ')}
        </p>
      )}
    </article>
  );
}

export default function RelatedDecisions({
  source,
  identifier,
  ementa,
  headingId,
}: RelatedDecisionsProps) {
  const [state, setState] = useState<State>({ status: 'loading' });
  const { search } = useLocation();

  useEffect(() => {
    // Mounted once per decision — the call site keys this block on the pair —
    // so there is no stale state to reset. The flag is for the answer that
    // lands after the reader has already moved on.
    const controller = new AbortController();
    let active = true;

    getRelatedDecisions(source, identifier, { signal: controller.signal, limit: LIMIT }).then(
      (relation) => {
        if (active) {
          setState({ status: 'loaded', relation });
        }
      },
      () => {
        if (active) {
          setState({ status: 'failed' });
        }
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [source, identifier]);

  const method =
    state.status === 'loaded' ? (state.relation.method ?? FALLBACK_METHOD) : FALLBACK_METHOD;

  return (
    <section className="neighbours" aria-labelledby={headingId}>
      <h3 id={headingId} className="decision-detail__section-title">
        Decisões sobre o mesmo assunto
      </h3>

      <p className="neighbours__lead">
        Relação por <strong>{method}</strong> desta ferramenta — o tribunal não apontou vínculo
        entre elas. Tratar do mesmo assunto não é decidir no mesmo sentido: uma destas pode ter
        decidido o contrário.
      </p>

      {state.status === 'loading' && (
        <p className="neighbours__state" role="status">
          Procurando decisões sobre o mesmo assunto…
        </p>
      )}

      {/* An answer and a failure read alike if they are written alike, and they
          are not the same news: the first means the comparison ran and found
          nothing close, the second that it did not run. */}
      {state.status === 'failed' && (
        <p className="neighbours__state neighbours__state--failed">
          <WarningCircle size={15} weight="fill" aria-hidden="true" />
          <span>
            Não foi possível procurar decisões próximas agora. A decisão acima está completa; só
            este bloco ficou de fora.
          </span>
        </p>
      )}

      {state.status === 'loaded' && state.relation.results.length === 0 && (
        <p className="neighbours__state">
          Nenhuma decisão próxima. A comparação rodou e não encontrou nada: ou esta ementa não traz
          termo raro o bastante para procurar, o que acontece com 1,7% do acervo, ou nenhuma outra
          decisão compartilha dois deles.
        </p>
      )}

      {state.status === 'loaded' && state.relation.results.length > 0 && (
        <div className="neighbours__list">
          {state.relation.results.map((neighbour) => (
            <Close
              key={`${neighbour.source}:${neighbour.identifier}`}
              neighbour={neighbour}
              ementa={ementa}
              search={search}
            />
          ))}
        </div>
      )}
    </section>
  );
}
