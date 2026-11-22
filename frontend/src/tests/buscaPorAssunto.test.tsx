import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function decision(identifier: string, snippet: string, extra: object = {}) {
  return {
    source: 'tjdft-jurisdf',
    identifier,
    court: 'TJDFT',
    case_number: `0000${identifier}-00.2026.8.07.0001`,
    judging_body: '1ª TURMA CÍVEL',
    reporting_judge: 'ANA CANTARINO',
    decided_on: '2026-03-01',
    small_claims: false,
    source_url: `https://jurisdf.tjdft.jus.br/detalhes/${identifier}`,
    source_url_reachable: true,
    snippet,
    ...extra,
  };
}

const POR_PALAVRA = [decision('1', 'Demora no voo e dano moral.')];

const REORDENADA = [
  decision('9', 'TRANSPORTE AÉREO. OVERBOOKING.', { by_subject: true, proximity: 'high' }),
  decision('1', 'Demora no voo e dano moral.', { by_subject: false, proximity: 'medium' }),
  decision('8', 'TRANSPORTE AÉREO. CANCELAMENTO.', { by_subject: true, proximity: 'low' }),
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function installApi() {
  const sent: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname !== '/decisions') {
        return json({ detail: 'Decision not found.' }, 404);
      }
      sent.push(url);
      const exatas = url.searchParams.get('mode') === 'exact';
      return json({
        total: exatas ? 1 : 3,
        page: 1,
        page_size: 20,
        results: exatas ? POR_PALAVRA : REORDENADA,
      });
    }),
  );
  return { sent, last: () => sent[sent.length - 1] };
}

async function pesquisar() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article');
  return user;
}

const cartoes = () => screen.getAllByRole('article');

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('o leitor escolhe como pesquisar', () => {
  it('oferece as duas opções sem nomear tecnologia', () => {
    installApi();
    renderApp();

    expect(screen.getByRole('radio', { name: 'Só as minhas palavras' })).toBeInTheDocument();
    expect(
      screen.getByRole('radio', { name: 'Palavras e assuntos parecidos' }),
    ).toBeInTheDocument();
  });

  it('começa na busca ampliada, que é o padrão da API, e não manda nada', async () => {
    const api = installApi();
    await pesquisar();

    expect(screen.getByRole('radio', { name: 'Palavras e assuntos parecidos' })).toBeChecked();
    expect(api.last().searchParams.has('mode')).toBe(false);
  });

  it('manda mode=exact quando o leitor pede só as suas palavras', async () => {
    const api = installApi();
    const user = await pesquisar();

    await user.click(screen.getByRole('radio', { name: 'Só as minhas palavras' }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    expect(api.last().searchParams.get('mode')).toBe('exact');
  });
});

describe('a lista reordenada por sentido', () => {
  it('mostra as decisões na ordem que a API mandou, sem separar em blocos', async () => {
    installApi();
    await pesquisar();

    expect(cartoes()).toHaveLength(3);
    expect(cartoes()[0]).toHaveTextContent('OVERBOOKING');
  });

  it('marca só as que a busca por palavra não encontrou', async () => {
    installApi();
    await pesquisar();

    const marcadas = cartoes().map(
      (cartao) => within(cartao).queryByText('assunto parecido') !== null,
    );

    expect(marcadas).toEqual([true, false, true]);
  });

  it('diz a proximidade em palavras que o leitor entende, não em porcentagem', async () => {
    installApi();
    await pesquisar();

    expect(within(cartoes()[0]).getByText('muito próximo')).toBeInTheDocument();
    expect(within(cartoes()[1]).getByText('próximo')).toBeInTheDocument();
    expect(within(cartoes()[2]).getByText('relacionado')).toBeInTheDocument();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it('não marca nem rotula nada quando o leitor pede só as suas palavras', async () => {
    installApi();
    const user = await pesquisar();

    await user.click(screen.getByRole('radio', { name: 'Só as minhas palavras' }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    expect(screen.queryByText('assunto parecido')).toBeNull();
    expect(screen.queryByText('muito próximo')).toBeNull();
  });

  it('não quebra contra uma API publicada antes da funcionalidade', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        if (url.pathname !== '/decisions') {
          return json({ detail: 'Decision not found.' }, 404);
        }
        return json({ total: 1, page: 1, page_size: 20, results: POR_PALAVRA });
      }),
    );
    await pesquisar();

    expect(cartoes().length).toBeGreaterThan(0);
    expect(screen.queryByText('assunto parecido')).toBeNull();
  });
});
