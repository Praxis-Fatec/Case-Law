import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Neighbour } from '../api/related';
import RelatedDecisions from '../components/RelatedDecisions';
import { spell } from '../components/stems';

// O mesmo que `doutrinaNoDetalhe` faz, e pelo mesmo motivo: `VITE_API_URL` vem
// do `.env`, que não é versionado. Sem isto a suíte passa na máquina de quem
// tem o arquivo e quebra no CI, que não tem.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

/**
 * The decisions suggested as treating the same subject, on the screen.
 *
 * `RF20` asks for three things this block has to keep, and two of them are
 * sentences rather than data: the method has to be stated, a computed relation
 * told apart from an official one, and the suggestions have to open. The third
 * is a link; the first two are only true if they are written, so they are
 * asserted here as text.
 *
 * The fourth promise is the project's own. The API answers stems, because a
 * stem is what matched; a reader asked to judge `poluidor-pag` cannot. So the
 * terms reach the screen spelled as the ementa spells them, never raw.
 */

// The ementa of the decision being read, which is where the stems are spelled
// from: it is already on screen, so no extra request is needed to say why.
const EMENTA =
  'RECURSO ESPECIAL. Indenização a pescador artesanal por poluição decorrente de ' +
  'derramamento de nafta. Princípio do poluidor-pagador. Responsabilidade objetiva.';

const PROXIMA: Neighbour = {
  source: 'stj-espelhos',
  identifier: '000525506',
  court: 'STJ',
  case_number: '0712598-03.2019.8.07.0003',
  judging_body: 'SEGUNDA SEÇÃO',
  reporting_judge: 'SIDNEI BENETI',
  decided_on: '2026-02-10',
  small_claims: false,
  source_url: 'https://scon.stj.jus.br/SCON/pesquisar.jsp?num_registro=000525506',
  source_url_reachable: true,
  source_url_shared: false,
  deliberation: 'unanime',
  similarity: 0.3841,
  terms: 31,
  matched_on: ['poluidor-pag', 'pescador', 'artesanal', 'derram', 'nafta', 'poluica'],
};

const OUTRA: Neighbour = {
  ...PROXIMA,
  identifier: '000711234',
  case_number: '0700002-22.2026.8.07.0001',
  similarity: 0.2104,
  matched_on: ['nafta', 'pescador'],
};

const METHOD = 'similaridade calculada';

function answering(body: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  });
}

// At the decision's own address, with a search in it: the suggestions have to
// carry that search along or following one would drop the list behind it.
function block(ementa = EMENTA) {
  return render(
    <MemoryRouter initialEntries={['/decisoes/stj-espelhos/1?q=nafta']}>
      <RelatedDecisions source="stj-espelhos" identifier="1" ementa={ementa} headingId="proximas" />
    </MemoryRouter>,
  );
}

const card = (container: HTMLElement) => container.querySelector('.neighbour') as HTMLElement;

beforeEach(() => {
  vi.stubGlobal('fetch', answering({ results: [], method: METHOD }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('o método, que a RF20 exige por escrito', () => {
  it('é dito antes do primeiro card', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(screen.getByText(/Relação por/)).toHaveTextContent(METHOD);
  });

  it('é dito também quando não há nenhuma próxima', async () => {
    block();

    await screen.findByText(/Nenhuma decisão próxima/);

    expect(screen.getByText(/Relação por/)).toHaveTextContent(METHOD);
  });

  it('é o que a resposta disse, e não um texto fixo na tela', async () => {
    // Quem decide o método é quem calculou. Uma tela que escreve o método na
    // mão deixa de dizer a verdade no dia em que o cálculo mudar.
    vi.stubGlobal(
      'fetch',
      answering({ results: [PROXIMA], method: 'similaridade calculada (vocabulário de 11/2026)' }),
    );
    block();

    expect(await screen.findByText(/vocabulário de 11\/2026/)).toBeInTheDocument();
  });

  it('distingue a relação calculada do vínculo oficial do tribunal', async () => {
    block();

    expect(await screen.findByText(/o tribunal não apontou vínculo/)).toBeInTheDocument();
  });

  it('avisa que tratar do mesmo assunto não é decidir no mesmo sentido', async () => {
    // A própria RF20 diz isto: proximidade semântica não prova identidade de
    // entendimento jurídico. Sem esta linha a tela sugere o contrário.
    block();

    expect(await screen.findByText(/pode ter decidido o contrário/)).toBeInTheDocument();
  });
});

describe('os quatro estados', () => {
  it('carregando diz que está procurando', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    block();

    expect(screen.getByRole('status')).toHaveTextContent(/Procurando decisões/);
  });

  it('com sugestões mostra cada decisão, com quem julgou e quando', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container)).toHaveTextContent('STJ · SEGUNDA SEÇÃO · 10/02/2026');
  });

  it('nenhuma encontrada é resposta, e diz por quê', async () => {
    block();

    const texto = await screen.findByText(/Nenhuma decisão próxima/);

    expect(texto).toHaveTextContent(/termo raro o bastante/);
    // Uma resposta não se anuncia como falha.
    expect(screen.queryByText(/Não foi possível procurar/)).not.toBeInTheDocument();
  });

  it('indisponível é falha, e não se parece com a resposta vazia', async () => {
    vi.stubGlobal('fetch', answering({ detail: 'A base não responde.' }, false));
    block();

    const falha = await screen.findByText(/Não foi possível procurar decisões próximas/);

    expect(falha).toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma decisão próxima/)).not.toBeInTheDocument();
  });

  it('a falha diz que a decisão continua inteira', async () => {
    // A regra de degradação, escrita na tela e não só no backend: quem lê
    // precisa saber que perdeu este bloco e nada mais.
    vi.stubGlobal('fetch', answering({}, false));
    block();

    expect(await screen.findByText(/A decisão acima está completa/)).toBeInTheDocument();
  });
});

describe('abrir a decisão sugerida', () => {
  it('cada sugestão é um link para o endereço da própria decisão', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    block();

    const link = await screen.findByRole('link', { name: /Processo 0712598/ });

    // Leva a busca junto: o endereço da decisão é filho da busca, e sem ela a
    // volta para a lista chega sem lista.
    expect(link).toHaveAttribute('href', '/decisoes/stj-espelhos/000525506?q=nafta');
  });

  it('nomeia a decisão sem processo em vez de deixar um link vazio', async () => {
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...PROXIMA, case_number: null }], method: METHOD }),
    );
    block();

    expect(await screen.findByRole('link', { name: /sem número de processo/ })).toBeInTheDocument();
  });

  it('descarta a sugestão que chega sem endereço', async () => {
    // Sem fonte e identificador não há endereço para abrir, e um card que não
    // abre nada é pior do que card nenhum.
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...PROXIMA, identifier: null }, OUTRA], method: METHOD }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(container.querySelectorAll('.neighbour')).toHaveLength(1);
  });
});

describe('o motivo da sugestão', () => {
  it('mostra os termos em comum como a ementa os escreve, não como radicais', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });
    const motivo = card(container);

    expect(within(motivo).getByText(/Termos em comum/)).toBeInTheDocument();
    expect(motivo).toHaveTextContent('poluidor-pagador');
    expect(motivo).toHaveTextContent('pescador');
    // O que falha aqui é alguém renderizar `matched_on` direto. O radical é
    // prefixo da palavra que o gerou, então o que se procura é ele sozinho —
    // `derramamento` passa, `derram` não.
    expect(motivo.textContent).not.toMatch(/\bpoluidor-pag\b/);
    expect(motivo.textContent).not.toMatch(/\bderram\b/);
    expect(motivo).toHaveTextContent('derramamento');
  });

  it('mostra no máximo quatro, para caber numa olhada', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    const motivo = container.querySelector('.neighbour__ground')?.textContent ?? '';
    expect(motivo.split(' · ')).toHaveLength(4);
    // Os quatro primeiros são os mais raros, que é a ordem em que a API manda.
    expect(motivo).not.toContain('poluição');
  });

  it('não promete motivo quando não veio termo nenhum', async () => {
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...PROXIMA, matched_on: [] }], method: METHOD }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(container.querySelector('.neighbour__ground')).toBeNull();
  });

  it('não mostra a nota: ela ordena a lista e não mede concordância', async () => {
    // Uma porcentagem ao lado de duas decisões é lida como "concordam em
    // 38%", que é exatamente o que a nota não diz.
    vi.stubGlobal('fetch', answering({ results: [PROXIMA], method: METHOD }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container).textContent).not.toContain('38');
    expect(card(container).textContent).not.toContain('0,38');
  });

  it('mantém a ordem em que a API mandou', async () => {
    vi.stubGlobal('fetch', answering({ results: [PROXIMA, OUTRA], method: METHOD }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    const processos = Array.from(container.querySelectorAll('.neighbour__case')).map(
      (item) => item.textContent,
    );
    expect(processos[0]).toContain('0712598');
    expect(processos[1]).toContain('0700002');
  });
});

describe('a lista', () => {
  it('abandona a resposta que chega depois de trocar de decisão', async () => {
    const lenta = vi.fn().mockReturnValue(new Promise(() => {}));
    vi.stubGlobal('fetch', lenta);

    const { unmount } = block();
    unmount();

    await waitFor(() => expect(lenta).toHaveBeenCalled());
  });
});

describe('o radical e a palavra', () => {
  it('escreve o radical com o acento que a ementa tem', () => {
    expect(spell('Indenização por poluição ambiental.', ['poluica'], 4)).toEqual(['poluição']);
  });

  it('entende o radical com hífen', () => {
    expect(spell('Princípio do poluidor-pagador.', ['poluidor-pag'], 4)).toEqual([
      'poluidor-pagador',
    ]);
  });

  it('não repete a mesma palavra por dois radicais', () => {
    expect(spell('Dano ambiental.', ['ambient', 'ambienta'], 4)).toEqual(['ambiental']);
  });

  it('deixa de fora o radical que a ementa não traz', () => {
    expect(spell('Dano ambiental.', ['nafta', 'ambient'], 4)).toEqual(['ambiental']);
  });

  it('respeita o limite pedido, e mantém a letra que a ementa usou', () => {
    expect(spell('Pescador artesanal e nafta.', ['pescador', 'artesanal', 'nafta'], 2)).toEqual([
      'Pescador',
      'artesanal',
    ]);
  });
});
