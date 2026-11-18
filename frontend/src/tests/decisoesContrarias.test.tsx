import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Contrary } from '../api/opposing';
import OpposingDecisions from '../components/OpposingDecisions';

// O mesmo que `decisoesProximas` faz, e pelo mesmo motivo: `VITE_API_URL` vem
// do `.env`, que não é versionado. Sem isto a suíte passa na máquina de quem
// tem o arquivo e quebra no CI, que não tem.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

/**
 * The decisions indicated as possibly contrary, on the screen.
 *
 * `RF23` asks for three things, and two of them are sentences rather than data:
 * the context compared and the reason for the indication have to be explained,
 * and the indication has to be distinguished from a definitive legal
 * conclusion. The third is a link. So the reason is asserted on every card and
 * the basis as text, because a sentence is only true if it is written.
 *
 * The fourth promise is this screen's own, and it is the one the endpoint was
 * shaped around: an unavailable answer must not read like an empty one.
 * "Nenhuma contrária" is a finding; 503 means nobody looked, and telling a
 * lawyer the first when the second happened is the one wrong answer here.
 */

const BASIS = 'leitura desta ferramenta';

const CONTRARIA: Contrary = {
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
  terms: 9,
  opposite_outcome: true,
  disagreements: [
    {
      court: 'STJ',
      kind: 'sumula',
      number: 85,
      this_decision: 'seguiu',
      other_decision: 'afastou',
    },
  ],
};

const OUTRA: Contrary = {
  ...CONTRARIA,
  identifier: '000711234',
  case_number: '0700002-22.2026.8.07.0001',
  similarity: 0.2104,
  terms: 3,
  opposite_outcome: false,
  disagreements: [
    {
      court: 'STJ',
      kind: 'sumula',
      number: 596,
      this_decision: 'afastou',
      other_decision: 'seguiu',
    },
  ],
};

function answering(body: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  });
}

// Uma resposta por chamada, na ordem em que foram pedidas: é assim que o
// segundo pedido — o que levanta o corte de 5 para 20 — se distingue do
// primeiro.
function answeringEach(...bodies: unknown[]) {
  const fetching = vi.fn();
  for (const body of bodies) {
    fetching.mockResolvedValueOnce({ ok: true, status: 200, json: async () => body });
  }
  return fetching;
}

// Tantas contrárias quantas o limite pedir, para exercitar o corte.
function many(total: number): Contrary[] {
  return Array.from({ length: total }, (_, index) => ({
    ...CONTRARIA,
    identifier: `9${String(index).padStart(5, '0')}`,
    case_number: `070000${index}-22.2026.8.07.0001`,
    opposite_outcome: false,
  }));
}

// No endereço da própria decisão, com uma busca nele: as contrárias têm de
// levar essa busca junto ou seguir uma delas derruba a lista de trás.
function block() {
  return render(
    <MemoryRouter initialEntries={['/decisoes/stj-espelhos/1?q=nafta']}>
      <OpposingDecisions source="stj-espelhos" identifier="1" headingId="contrarias" />
    </MemoryRouter>,
  );
}

const card = (container: HTMLElement) => container.querySelector('.contrary') as HTMLElement;

beforeEach(() => {
  vi.stubGlobal('fetch', answering({ results: [], basis: BASIS }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('a base da indicação, que a RF23 exige por escrito', () => {
  it('é dita antes do primeiro card', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(screen.getByText(/Indicação por/)).toHaveTextContent(BASIS);
  });

  it('é dita também quando não há nenhuma contrária', async () => {
    block();

    await screen.findByText(/Nenhuma decisão contrária/);

    expect(screen.getByText(/Indicação por/)).toHaveTextContent(BASIS);
  });

  it('é o que a resposta disse, e não um texto fixo na tela', async () => {
    // Quem decide a base é quem a produziu. Uma tela que escreve a base na mão
    // deixa de dizer a verdade no dia em que a regra mudar.
    vi.stubGlobal(
      'fetch',
      answering({ results: [CONTRARIA], basis: 'leitura desta ferramenta (regra de 11/2026)' }),
    );
    block();

    expect(await screen.findByText(/regra de 11\/2026/)).toBeInTheDocument();
  });

  it('distingue a indicação de um conflito declarado pelo tribunal', async () => {
    // A exigência literal da RF23: a indicação não pode passar por conclusão
    // jurídica definitiva.
    block();

    expect(await screen.findByText(/o tribunal não declarou conflito/)).toBeInTheDocument();
  });

  it('explica o que torna duas decisões contrárias antes de listar nenhuma', async () => {
    block();

    const chamada = await screen.findByText(/Indicação por/);

    expect(chamada).toHaveTextContent(/precedente que as duas citam/);
    expect(chamada).toHaveTextContent(/seguiu/);
    expect(chamada).toHaveTextContent(/afastou/);
    expect(chamada).toHaveTextContent(/distinguiu/);
  });
});

describe('os três estados', () => {
  it('carregando diz que está procurando', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    block();

    expect(screen.getByRole('status')).toHaveTextContent(/Procurando decisões contrárias/);
  });

  it('com contrárias mostra cada decisão, com quem julgou e quando', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container)).toHaveTextContent('STJ · SEGUNDA SEÇÃO · 10/02/2026');
  });

  it('nenhuma encontrada é resposta, e diz que é a resposta comum', async () => {
    block();

    const texto = await screen.findByText(/Nenhuma decisão contrária/);

    expect(texto).toHaveTextContent(/dezenove decisões em vinte/);
    expect(texto).toHaveTextContent(/A regra rodou/);
    // Uma resposta não se anuncia como falha.
    expect(screen.queryByText(/Não foi possível procurar/)).not.toBeInTheDocument();
  });

  it('indisponível é falha, e nunca a lista vazia', async () => {
    // O endpoint responde 503 em vez de lista vazia exatamente para que esta
    // tela possa dizer "não rodou". Se este teste cair, alguém transformou a
    // falha em "nenhuma contrária" — a única resposta errada que a RF23 não
    // pode dar.
    vi.stubGlobal('fetch', answering({ detail: 'A tabela não está publicada.' }, false));
    block();

    const falha = await screen.findByText(/Não foi possível procurar decisões contrárias/);

    expect(falha).toHaveTextContent(/não quer dizer que não existam/);
    expect(screen.queryByText(/Nenhuma decisão contrária/)).not.toBeInTheDocument();
  });

  it('a falha diz que a decisão continua inteira', async () => {
    vi.stubGlobal('fetch', answering({}, false));
    block();

    expect(await screen.findByText(/A decisão acima está completa/)).toBeInTheDocument();
  });
});

describe('o motivo da indicação', () => {
  it('nomeia o precedente em disputa e o que cada decisão fez com ele', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });
    const motivo = within(card(container)).getByRole('listitem');

    expect(motivo).toHaveTextContent('Súmula 85 do STJ');
    expect(motivo).toHaveTextContent(/esta decisão seguiu, a outra afastou/);
  });

  it('um par que disputa dois precedentes é uma entrada com dois motivos', async () => {
    // Duas linhas na tabela e uma decisão na tela. Deixar passar como duas
    // entradas mostraria o mesmo processo duas vezes.
    vi.stubGlobal(
      'fetch',
      answering({
        results: [
          {
            ...CONTRARIA,
            disagreements: [
              ...CONTRARIA.disagreements,
              {
                court: 'STJ',
                kind: 'sumula',
                number: 596,
                this_decision: 'seguiu',
                other_decision: 'distinguiu',
              },
            ],
          },
        ],
        basis: BASIS,
      }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(container.querySelectorAll('.contrary')).toHaveLength(1);
    const motivos = within(card(container)).getAllByRole('listitem');
    expect(motivos).toHaveLength(2);
    expect(motivos[1]).toHaveTextContent('Súmula 596 do STJ');
    expect(motivos[1]).toHaveTextContent(/a outra distinguiu/);
  });

  it('diz o contexto comparado, que é o que a RF23 chama de contexto', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container)).toHaveTextContent('9 termos raros em comum');
  });

  it('descarta a entrada que chega sem motivo nenhum', async () => {
    // Uma indicação sem motivo é o ruído com cara de análise que a história
    // existe para evitar. Melhor card nenhum.
    vi.stubGlobal(
      'fetch',
      answering({
        results: [{ ...CONTRARIA, disagreements: [] }, OUTRA],
        basis: BASIS,
      }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(container.querySelectorAll('.contrary')).toHaveLength(1);
  });

  it('descarta a entrada cujo motivo chega sem as duas aderências', async () => {
    vi.stubGlobal(
      'fetch',
      answering({
        results: [
          {
            ...CONTRARIA,
            disagreements: [{ court: 'STJ', kind: 'sumula', number: 85, this_decision: 'seguiu' }],
          },
          OUTRA,
        ],
        basis: BASIS,
      }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(container.querySelectorAll('.contrary')).toHaveLength(1);
  });

  it('descarta a entrada que chega sem endereço', async () => {
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...CONTRARIA, identifier: null }, OUTRA], basis: BASIS }),
    );
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(container.querySelectorAll('.contrary')).toHaveLength(1);
  });

  it('não mostra a nota de semelhança: ela ordena a lista e não mede contradição', async () => {
    // Uma porcentagem ao lado de duas decisões contrárias é lida como
    // "contradizem em 38%", que é exatamente o que a nota não diz.
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container).textContent).not.toContain('38');
    expect(card(container).textContent).not.toContain('0,38');
  });

  it('mantém a ordem em que a API mandou', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA, OUTRA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    const processos = Array.from(container.querySelectorAll('.contrary__case')).map(
      (item) => item.textContent,
    );
    expect(processos[0]).toContain('0712598');
    expect(processos[1]).toContain('0700002');
  });
});

describe('o resultado oposto, que é contexto e não motivo', () => {
  it('aparece ao lado da entrada', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    const { container } = block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    expect(card(container)).toHaveTextContent('Resultados opostos');
  });

  it('vem com a medição que diz o quanto ele vale', async () => {
    // Sem esta nota o leitor conclui o contrário do que foi medido: decisões
    // parecidas divergem no resultado MENOS do que pares aleatórios.
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    block();

    await screen.findByRole('link', { name: /Processo 0712598/ });

    const nota = screen.getByText(/nunca o motivo da indicação/);
    expect(nota).toHaveTextContent('11,9%');
    expect(nota).toHaveTextContent('25,7%');
    expect(nota).toHaveTextContent(/qual parte recorreu/);
  });

  it('não explica o que não está na tela', async () => {
    vi.stubGlobal('fetch', answering({ results: [OUTRA], basis: BASIS }));
    block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(screen.queryByText(/nunca o motivo da indicação/)).not.toBeInTheDocument();
    expect(screen.queryByText('Resultados opostos')).not.toBeInTheDocument();
  });
});

describe('o corte da lista', () => {
  it('não avisa corte nenhum quando a lista não encheu', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA, OUTRA], basis: BASIS }));
    block();

    await screen.findByRole('link', { name: /Processo 0700002/ });

    expect(screen.queryByText(/Mostrando as/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mostrar até/ })).not.toBeInTheDocument();
  });

  it('avisa que cortou quando a lista encheu, em vez de parecer completa', async () => {
    // A medição diz que a mediana das decisões que têm alguma contrária tem 21
    // delas, e a pior do acervo tem 1.266. Mostrar cinco sem dizer que são
    // cinco de muitas é a tela afirmando o que não mediu.
    vi.stubGlobal('fetch', answering({ results: many(5), basis: BASIS }));
    block();

    const aviso = await screen.findByText(/Mostrando as 5 mais próximas/);

    expect(aviso).toHaveTextContent(/Pode haver outras/);
    expect(screen.getByRole('button', { name: /Mostrar até 20/ })).toBeInTheDocument();
  });

  it('pede as primeiras cinco, e só vai a vinte quando o leitor pede', async () => {
    const fetching = answeringEach(
      { results: many(5), basis: BASIS },
      { results: many(12), basis: BASIS },
    );
    vi.stubGlobal('fetch', fetching);
    const { container } = block();

    await screen.findByRole('button', { name: /Mostrar até 20/ });
    expect(String(fetching.mock.calls[0][0])).toContain('limit=5');

    await userEvent.click(screen.getByRole('button', { name: /Mostrar até 20/ }));

    await waitFor(() => expect(container.querySelectorAll('.contrary')).toHaveLength(12));
    expect(String(fetching.mock.calls[1][0])).toContain('limit=20');
  });

  it('para de oferecer mais quando chegou ao máximo que o endpoint aceita', async () => {
    const fetching = answeringEach(
      { results: many(5), basis: BASIS },
      { results: many(20), basis: BASIS },
    );
    vi.stubGlobal('fetch', fetching);
    block();

    await userEvent.click(await screen.findByRole('button', { name: /Mostrar até 20/ }));

    const aviso = await screen.findByText(/Mostrando as 20 mais próximas/);
    expect(aviso).toHaveTextContent(/o máximo que esta tela pede/);
    expect(screen.queryByRole('button', { name: /Mostrar até/ })).not.toBeInTheDocument();
  });
});

describe('abrir a decisão contrária', () => {
  it('cada entrada é um link para o endereço da própria decisão', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONTRARIA], basis: BASIS }));
    block();

    const link = await screen.findByRole('link', { name: /Processo 0712598/ });

    // Leva a busca junto: o endereço da decisão é filho da busca, e sem ela a
    // volta para a lista chega sem lista.
    expect(link).toHaveAttribute('href', '/decisoes/stj-espelhos/000525506?q=nafta');
  });

  it('nomeia a decisão sem processo em vez de deixar um link vazio', async () => {
    vi.stubGlobal(
      'fetch',
      answering({ results: [{ ...CONTRARIA, case_number: null }], basis: BASIS }),
    );
    block();

    expect(await screen.findByRole('link', { name: /sem número de processo/ })).toBeInTheDocument();
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
