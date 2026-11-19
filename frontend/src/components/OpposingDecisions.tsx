import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, WarningCircle } from '@phosphor-icons/react';

import { getOpposingDecisions, type Contrary, type Opposition } from '../api/opposing';
import { detailPath } from './decisionAddress';
import { formatDate, normalizeText } from './decisionFormat';
import { precedentName } from './precedentFormat';

/**
 * Decisions that may contradict the one being read — `RF23`.
 *
 * The reason is the whole feature. Two decisions are shown as contrary because
 * they cite the same precedent and treated it in opposite ways — one followed
 * it, the other departed from it or distinguished it — which is a disagreement
 * the court itself wrote down. So every card names the precedent and what each
 * decision did with it, and an entry that arrives without that is dropped in
 * `api/opposing.ts` rather than shown as an indication with no stated ground.
 *
 * Opposite outcome is not the reason, and this is where that matters most. The
 * measurement in `opposing-decisions.md` found similar decisions disagreeing on
 * the outcome *less* often than random pairs, so it travels as context beside
 * the entry and the note under the list says what it is worth.
 *
 * Two states that look alike elsewhere are kept apart here. An empty list means
 * the rule ran and found nothing, which is the ordinary answer for nineteen
 * decisions in twenty. A failure means it did not run, and the endpoint answers
 * 503 instead of an empty list precisely so this screen can say so: telling a
 * lawyer there is no contradiction when nobody looked is the one wrong answer
 * it cannot afford.
 *
 * Placed after the decisions on the same subject. Those are near this one; these
 * disagree with it, and reading the second only makes sense after the first.
 */

type OpposingDecisionsProps = {
  source: string;
  identifier: string;
  headingId: string;
};

type State =
  { status: 'loading' } | { status: 'loaded'; opposition: Opposition } | { status: 'failed' };

// Five is a cut, not a ceiling: the median decision that has any contrary has
// twenty-one of them. The endpoint refuses anything above twenty, which is why
// the second ask stops there and the line above the button says the list was
// cut instead of letting it look complete.
const FIRST_LIMIT = 5;
const MOST = 20;

// Said when the answer does not say, which only happens against an API older
// than this screen. Never guessed into something stronger — `RF23` requires the
// indication to be told apart from a settled legal conclusion, and an unstated
// basis is not a conclusion of the court.
const FALLBACK_BASIS = 'leitura desta ferramenta';

function Opposed({ contrary, search }: { contrary: Contrary; search: string }) {
  const caseNumber = normalizeText(contrary.case_number);
  const decided = formatDate(contrary.decided_on);
  const byline = [normalizeText(contrary.court), normalizeText(contrary.judging_body), decided]
    .filter(Boolean)
    .join(' · ');
  const name = caseNumber ? `Processo ${caseNumber}` : 'Decisão sem número de processo informado';

  return (
    <article className="contrary" aria-label={name}>
      <h4 className="contrary__case">
        {/* The search travels with the address, as in every other suggestion on
            this screen: the decision's address is a child of the search, and
            Back without it comes back to no list. */}
        <Link className="contrary__link" to={{ pathname: detailPath(contrary), search }}>
          {name}
          <ArrowRight size={14} weight="bold" aria-hidden="true" />
        </Link>
      </h4>

      {byline && <p className="contrary__byline">{byline}</p>}

      <ul className="contrary__reasons">
        {contrary.disagreements.map((disagreement) => (
          <li
            key={`${disagreement.court}:${disagreement.kind}:${disagreement.number}`}
            className="contrary__reason"
          >
            <span className="contrary__precedent">{precedentName(disagreement)}</span>
            <span className="contrary__sides">
              esta decisão <strong>{disagreement.this_decision}</strong>, a outra{' '}
              <strong>{disagreement.other_decision}</strong>
            </span>
          </li>
        ))}
      </ul>

      {(contrary.terms !== null || contrary.opposite_outcome) && (
        <p className="contrary__context">
          {contrary.terms !== null && (
            <span className="contrary__terms">{contrary.terms} termos raros em comum</span>
          )}
          {contrary.opposite_outcome && <span className="contrary__flag">Resultados opostos</span>}
        </p>
      )}
    </article>
  );
}

export default function OpposingDecisions({
  source,
  identifier,
  headingId,
}: OpposingDecisionsProps) {
  const [state, setState] = useState<State>({ status: 'loading' });
  const [limit, setLimit] = useState(FIRST_LIMIT);
  // Only the second ask. The first one is the block's own loading state; this
  // one keeps the list on screen while a longer one is fetched, because the
  // reader asked for more of something they are already reading.
  const [pending, setPending] = useState(false);
  const { search } = useLocation();

  useEffect(() => {
    // Mounted once per decision — the call site keys this block on the pair —
    // so there is no stale state to reset between decisions. The flag is for
    // the answer that lands after the reader has already moved on.
    const controller = new AbortController();
    let active = true;

    getOpposingDecisions(source, identifier, { signal: controller.signal, limit }).then(
      (opposition) => {
        if (active) {
          setState({ status: 'loaded', opposition });
          setPending(false);
        }
      },
      () => {
        if (active) {
          setState({ status: 'failed' });
          setPending(false);
        }
      },
    );

    return () => {
      active = false;
      controller.abort();
    };
  }, [source, identifier, limit]);

  const basis =
    state.status === 'loaded' ? (state.opposition.basis ?? FALLBACK_BASIS) : FALLBACK_BASIS;
  const found = state.status === 'loaded' ? state.opposition.results : [];
  // At the limit the list was cut, and there is no way to know by how much: the
  // answer carries no total. So the screen says it was cut and never invents a
  // number it was not told.
  const cut = found.length >= limit;

  return (
    <section className="contraries" aria-labelledby={headingId} aria-busy={pending}>
      <h3 id={headingId} className="decision-detail__section-title">
        Decisões que podem contradizer esta
      </h3>

      <p className="contraries__lead">
        Indicação por <strong>{basis}</strong> — o tribunal não declarou conflito entre elas. O
        motivo é sempre um precedente que as duas citam e trataram de formas opostas: uma o aplicou
        (<em>seguiu</em>) e a outra não o aplicou (<em>afastou</em>) ou diferenciou o caso (
        <em>distinguiu</em>).
      </p>

      {state.status === 'loading' && (
        <p className="contraries__state" role="status">
          Procurando decisões contrárias…
        </p>
      )}

      {/* The distinction this block exists to keep: a failure is not an answer.
          The endpoint answers 503 rather than an empty list so that "não
          rodou" can be said out loud instead of passing for "não existe". */}
      {state.status === 'failed' && (
        <p className="contraries__state contraries__state--failed">
          <WarningCircle size={15} weight="fill" aria-hidden="true" />
          <span>
            Não foi possível procurar decisões contrárias agora. Isso não quer dizer que não
            existam: a busca não rodou. A decisão acima está completa; só este bloco ficou de fora.
          </span>
        </p>
      )}

      {state.status === 'loaded' && found.length === 0 && (
        <p className="contraries__state">
          Nenhuma decisão contrária conhecida. É a resposta comum — dezenove decisões em vinte não
          têm nenhuma. A regra rodou e não achou outra decisão que tenha tratado de forma oposta um
          precedente citado por esta.
        </p>
      )}

      {state.status === 'loaded' && found.length > 0 && (
        <>
          <div className="contraries__list">
            {found.map((contrary) => (
              <Opposed
                key={`${contrary.source}:${contrary.identifier}`}
                contrary={contrary}
                search={search}
              />
            ))}
          </div>

          {found.some((contrary) => contrary.opposite_outcome) && (
            <p className="contraries__note">
              <strong>Resultados opostos</strong> é contexto, e nunca o motivo da indicação: medido
              no acervo, decisões parecidas divergem no resultado menos do que pares aleatórios —
              11,9% contra 25,7% — e o acervo não registra qual parte recorreu.
            </p>
          )}

          {cut && (
            <div className="contraries__more">
              <p className="contraries__cut">
                {limit < MOST
                  ? `Mostrando as ${found.length} mais próximas desta decisão. Pode haver outras: metade das decisões que têm alguma contrária tem 21 ou mais.`
                  : `Mostrando as ${found.length} mais próximas desta decisão, o máximo que esta tela pede. Pode haver outras.`}
              </p>

              {limit < MOST && (
                <button
                  type="button"
                  className="contraries__expand"
                  onClick={() => {
                    setPending(true);
                    setLimit(MOST);
                  }}
                  disabled={pending}
                >
                  {pending ? 'Procurando…' : `Mostrar até ${MOST}`}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
