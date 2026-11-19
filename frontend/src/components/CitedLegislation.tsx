import { useEffect, useState } from 'react';
import { WarningCircle } from '@phosphor-icons/react';

import { getCitedLegislation, type CitedLegislation as Reference } from '../api/legislation';
import { referenceLabel } from './legislationFormat';

/**
 * The laws and articles the decision applied.
 *
 * Everything here is the court's: the references come out of a field the court
 * itself writes in a fixed format, so this block carries no reading of ours and
 * no inference — which is why it has no counterpart to the precedents block's
 * rule and robot icon. What it has instead is a third state those blocks do not
 * need: a reference the parser could not read, shown as the court's own text
 * rather than dropped. Dropping it would show a decision applying less law than
 * it did, and nothing on the screen would say so.
 *
 * Nothing links out. Every candidate portal keys a statute differently from the
 * way this citation is built, and a link that opens the wrong law is worse than
 * a citation the reader looks up themselves.
 *
 * It fetches on its own, like the doctrine block: the decision is already on
 * screen when this starts, and a failure here turns into one line inside this
 * block and stops there.
 */

type CitedLegislationProps = { source: string; identifier: string; headingId: string };

type State =
  { status: 'loading' } | { status: 'loaded'; references: Reference[] } | { status: 'failed' };

function Entry({ reference }: { reference: Reference }) {
  const label = referenceLabel(reference);

  // Recognised and readable: the citation as a petition would write it.
  if (reference.recognised && label) {
    return (
      <li className="legislation__item">
        <span className="legislation__citation">{label}</span>
      </li>
    );
  }

  return (
    <li className="legislation__item legislation__item--raw">
      <p className="legislation__raw-note">
        Referência em formato que esta ferramenta não reconheceu. É o texto do tribunal, como ele
        veio:
      </p>
      {reference.raw ? (
        <code className="legislation__raw">{reference.raw}</code>
      ) : (
        <p className="legislation__raw-note">
          O tribunal registrou a referência sem conteúdo nenhum.
        </p>
      )}
    </li>
  );
}

export default function CitedLegislation({ source, identifier, headingId }: CitedLegislationProps) {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    // Mounted once per decision — the call site keys this block on the pair —
    // so there is no stale state to reset. The flag is for the answer that
    // lands after the reader has already moved on.
    const controller = new AbortController();
    let active = true;

    getCitedLegislation(source, identifier, { signal: controller.signal }).then(
      (references) => {
        if (active) {
          setState({ status: 'loaded', references });
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

  return (
    <section className="legislation" aria-labelledby={headingId}>
      <h3 id={headingId} className="decision-detail__section-title">
        Legislação citada
      </h3>

      <p className="legislation__lead">
        As normas que o próprio tribunal registrou nesta decisão. Nenhuma delas abre em portal de
        legislação: a citação é conferida na fonte oficial da norma, e um link para a lei errada é
        pior do que link nenhum.
      </p>

      {state.status === 'loading' && (
        <p className="legislation__state" role="status">
          Procurando a legislação citada…
        </p>
      )}

      {/* A failure and an answer must not read alike: the first means the
          lookup did not happen, the second that the court catalogued none. */}
      {state.status === 'failed' && (
        <p className="legislation__state legislation__state--failed">
          <WarningCircle size={15} weight="fill" aria-hidden="true" />
          <span>
            Não foi possível consultar a legislação agora. A decisão acima está completa; só este
            bloco ficou de fora.
          </span>
        </p>
      )}

      {state.status === 'loaded' && state.references.length === 0 && (
        <p className="legislation__state">
          Nenhuma referência legislativa catalogada nesta decisão. O tribunal não registrou nenhuma
          — o que não quer dizer que o acórdão não aplique lei, e sim que a lista de referências
          veio vazia.
        </p>
      )}

      {state.status === 'loaded' && state.references.length > 0 && (
        <ul className="legislation__list">
          {state.references.map((reference, index) => (
            <Entry key={`${reference.raw ?? 'vazia'}:${index}`} reference={reference} />
          ))}
        </ul>
      )}
    </section>
  );
}
