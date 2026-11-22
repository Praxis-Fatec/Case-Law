import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function decision(identifier: string, snippet: string) {
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
  };
}

const POR_PALAVRA = [{ ...decision('1', 'Demora no voo e dano moral.'), proximity: 'high' }];
const POR_ASSUNTO = [
  { ...decision('9', 'TRANSPORTE AÉREO. OVERBOOKING.'), proximity: 'medium' },
  { ...decision('8', 'TRANSPORTE AÉREO. CANCELAMENTO DO VOO.'), proximity: 'low' },
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function installApi(subjectMatches = POR_ASSUNTO) {
  const sent: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname !== '/decisions') {
        return json({ detail: 'Decision not found.' }, 404);
      }
      sent.push(url);
      return json({
        total: 1,
        page: 1,
        page_size: 20,
        results: POR_PALAVRA,
        subject_matches: url.searchParams.get('mode') === 'exact' ? [] : subjectMatches,
        ...(url.searchParams.get('mode') === 'exact'
          ? { results: POR_PALAVRA.map(({ proximity: _p, ...resto }) => resto) }
          : {}),
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

const bloco = () => screen.queryByRole('region', { name: 'Também sobre o mesmo assunto' });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('o leitor escolhe como pesquisar', () => {
  it('oferece as duas opções sem nomear tecnologia', () => {
    installApi();
    renderApp();

    expect(screen.getByRole('radio', { name: 'Palavras exatas' })).toBeInTheDocument();
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

  it('manda mode=exact quando o leitor pede palavras exatas', async () => {
    const api = installApi();
    const user = await pesquisar();

    await user.click(screen.getByRole('radio', { name: 'Palavras exatas' }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));

    expect(api.last().searchParams.get('mode')).toBe('exact');
  });
});

describe('o bloco de decisões por assunto', () => {
  it('aparece abaixo dos resultados, com a explicação em uma linha', async () => {
    installApi();
    await pesquisar();

    const secao = bloco();
    expect(secao).not.toBeNull();
    expect(
      within(secao!).getByText(/não aparecem na busca pelas palavras que você escreveu/i),
    ).toBeInTheDocument();
  });

  it('marca cada decisão como achada por assunto', async () => {
    installApi();
    await pesquisar();

    const cartoes = within(bloco()!).getAllByRole('article');

    expect(cartoes).toHaveLength(2);
    for (const cartao of cartoes) {
      expect(within(cartao).getByText('assunto parecido')).toBeInTheDocument();
    }
  });

  it('não marca as decisões achadas pelas palavras digitadas', async () => {
    installApi();
    await pesquisar();

    const porPalavra = screen
      .getAllByRole('article')
      .filter((cartao) => !bloco()!.contains(cartao));

    expect(porPalavra.length).toBeGreaterThan(0);
    for (const cartao of porPalavra) {
      expect(within(cartao).queryByText('assunto parecido')).toBeNull();
    }
  });

  it('some quando o leitor pede palavras exatas', async () => {
    installApi();
    const user = await pesquisar();

    await user.click(screen.getByRole('radio', { name: 'Palavras exatas' }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    expect(bloco()).toBeNull();
  });

  it('não aparece quando nada no acervo está perto o bastante', async () => {
    installApi([]);
    await pesquisar();

    expect(bloco()).toBeNull();
  });

  it('não quebra contra uma API publicada antes da funcionalidade', async () => {
    const sent: URL[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        if (url.pathname !== '/decisions') {
          return json({ detail: 'Decision not found.' }, 404);
        }
        sent.push(url);
        return json({ total: 1, page: 1, page_size: 20, results: POR_PALAVRA });
      }),
    );
    await pesquisar();

    expect(bloco()).toBeNull();
    expect(screen.getAllByRole('article').length).toBeGreaterThan(0);
  });
});

describe('a proximidade do que foi digitado', () => {
  it('aparece em palavras que o leitor entende, não em porcentagem', async () => {
    installApi();
    await pesquisar();

    expect(screen.getAllByText('muito próximo').length).toBeGreaterThan(0);
    expect(within(bloco()!).getByText('próximo')).toBeInTheDocument();
    expect(within(bloco()!).getByText('relacionado')).toBeInTheDocument();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it('não aparece na busca por palavras exatas, que não calcula sentido', async () => {
    installApi();
    const user = await pesquisar();

    await user.click(screen.getByRole('radio', { name: 'Palavras exatas' }));
    await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
    await screen.findAllByRole('article');

    expect(screen.queryByText('muito próximo')).toBeNull();
  });
});
