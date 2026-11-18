import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Decision } from '../api/decisions';
import { bookmarkKey, type SavedDecision } from '../api/savedDecisions';
import type { SavedSearch } from '../api/savedSearches';
import { rememberSession } from '../api/token';
import { resetBuffer } from '../search/resultsBuffer';
import { currentAddress, renderApp } from './renderApp';

// Keep the real components, routes, providers and request code. Only HTTP
// responses are controlled, so a broken button or request cannot pass through
// a mocked save/resume callback.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

const decision = (identifier: string): Decision => ({
  source: 'tjdft-jurisdf',
  identifier,
  court: 'TJDFT',
  // Two decisions from one case must remain separate bookmarks.
  case_number: '0700001-11.2026.8.07.0001',
  judging_body: '1ª TURMA CÍVEL',
  reporting_judge: `RELATOR ${identifier}`,
  decided_on: '2026-03-10',
  small_claims: false,
  source_url: `https://jurisdf.tjdft.jus.br/detalhes/${identifier}`,
  source_url_reachable: true,
  source_url_shared: false,
  class_code: 198,
  judged_on: '2026-03-10',
  published_on: '2026-03-15',
  summary: `Ementa atual da decisão ${identifier}.`,
  outcome: null,
  thesis: [],
  deliberation: null,
  full_text_available: true,
  sections: null,
});
const FIRST = decision('2000001');
const SECOND = decision('2000002');
const savedDecision = (item: Decision): SavedDecision => ({
  source: item.source,
  identifier: item.identifier,
  court: item.court,
  case_number: item.case_number,
  summary: `Trecho salvo da decisão ${item.identifier}.`,
  decided_on: item.decided_on,
  created_at: '2026-11-17T12:00:00Z',
  available: true,
});
const SEARCH: SavedSearch = {
  id: 'search-1',
  name: 'Minha pesquisa de dano moral',
  created_at: '2026-11-17T12:00:00Z',
  filters: { q: 'dano moral', tribunal: ['TJDFT'], order: 'date', date_from: '2026-01-01' },
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function api(initialSearches: SavedSearch[] = [], initialDecisions: SavedDecision[] = []) {
  let searches = [...initialSearches];
  let decisions = [...initialDecisions];
  let searchNumber = 0;
  const requests: { url: URL; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      const method = init.method ?? 'GET';
      requests.push({ url, init });
      if (url.pathname === '/saved-decisions') {
        if (method === 'GET') return json({ decisions });
        if (method === 'POST') {
          const key = JSON.parse(String(init.body));
          const found = [FIRST, SECOND].find((item) => bookmarkKey(item) === bookmarkKey(key));
          if (!found) return json({}, 404);
          const saved = savedDecision(found);
          decisions = [
            saved,
            ...decisions.filter((item) => bookmarkKey(item) !== bookmarkKey(saved)),
          ];
          return json(saved, 201);
        }
      }
      if (url.pathname.startsWith('/saved-decisions/') && method === 'DELETE') {
        const [, , source, identifier] = url.pathname.split('/').map(decodeURIComponent);
        decisions = decisions.filter(
          (item) => item.source !== source || item.identifier !== identifier,
        );
        return new Response(null, { status: 204 });
      }
      if (url.pathname === '/searches') {
        if (method === 'POST') {
          const saved = { ...SEARCH, ...JSON.parse(String(init.body)) };
          searches = [saved, ...searches];
          return json(saved, 201);
        }
        return json({ searches });
      }
      if (url.pathname === '/searches/search-1') {
        if (method === 'DELETE') {
          searches = searches.filter((item) => item.id !== SEARCH.id);
          return new Response(null, { status: 204 });
        }
        return searches.length ? json(searches[0]) : json({}, 404);
      }
      if (url.pathname === '/decisions') {
        searchNumber += 1;
        return json({
          total: 2,
          page: 1,
          page_size: 60,
          results: [FIRST, SECOND].map((item) => ({
            ...item,
            snippet: `Resultado atualizado ${searchNumber}: ${item.identifier}.`,
          })),
        });
      }
      const detail = [FIRST, SECOND].find(
        (item) => url.pathname === `/decisions/${item.source}/${item.identifier}`,
      );
      if (detail) return json(detail);
      if (/\/(doctrine|legislation|related|opposing)$/.test(url.pathname))
        return json({ results: [] });
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'TJDFT', name: 'TJDFT' }] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      throw new Error(`Unexpected request: ${method} ${url.pathname}`);
    }),
  );
  return { requests, records: () => ({ searches, decisions }) };
}

const drawer = () => within(screen.getByRole('dialog', { name: 'Itens salvos' }));
const openItems = () => fireEvent.click(screen.getByRole('link', { name: /Itens salvos/ }));
async function search() {
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'dano moral' } });
  fireEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findAllByRole('article', { name: `Decisão ${FIRST.case_number}` });
}
function expectAuthenticated(requests: ReturnType<typeof api>['requests']) {
  for (const { init } of requests)
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer saved-items-flow-token');
}
beforeEach(() => {
  resetBuffer();
  rememberSession('saved-items-flow-token');
  Element.prototype.scrollIntoView = vi.fn();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});
afterEach(() => {
  rememberSession(null);
  vi.unstubAllGlobals();
});

describe('SCRUM-270 — saved items through the real application', () => {
  it('saves a named search and a decision from the result, without opening the result link', async () => {
    const server = api();
    renderApp();
    await search();
    const [first] = screen.getAllByRole('article', { name: `Decisão ${FIRST.case_number}` });
    const save = within(first).getByRole('button', { name: 'Salvar decisão' });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await within(first).findByRole('button', { name: 'Remover decisão dos itens salvos' });
    expect(currentAddress()).toBe('/');
    const detail = screen.getByRole('complementary');
    expect(
      await within(detail).findByRole('button', { name: 'Remover decisão dos itens salvos' }),
    ).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Salvar pesquisa' }));
    const form = within(screen.getByRole('dialog', { name: 'Salvar pesquisa' }));
    fireEvent.change(form.getByRole('textbox', { name: 'Nome da pesquisa' }), {
      target: { value: SEARCH.name },
    });
    fireEvent.click(form.getByRole('button', { name: 'Salvar pesquisa' }));
    await screen.findByRole('button', { name: 'Pesquisa salva' });
    const post = server.requests.find(
      ({ url, init }) => url.pathname === '/saved-decisions' && init.method === 'POST',
    )!;
    expect(JSON.parse(String(post.init.body))).toEqual({
      source: FIRST.source,
      identifier: FIRST.identifier,
    });
    expect(server.records().searches[0]).toMatchObject({
      name: SEARCH.name,
      filters: { q: 'dano moral' },
    });
    expect(server.records().decisions).toHaveLength(1);
    expectAuthenticated(server.requests);
  });

  it('lists the two categories with their counts and distinguishes decisions of the same case', async () => {
    api([SEARCH], [savedDecision(FIRST), savedDecision(SECOND)]);
    renderApp('/salvas');
    expect(await drawer().findByRole('article', { name: SEARCH.name })).toBeVisible();
    expect(drawer().getByRole('button', { name: 'Pesquisas 1' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    fireEvent.click(await drawer().findByRole('button', { name: 'Decisões 2' }));
    expect(drawer().queryByRole('article', { name: SEARCH.name })).not.toBeInTheDocument();
    expect(drawer().getAllByRole('article')).toHaveLength(2);
    expect(
      drawer()
        .getAllByRole('link', { name: 'Abrir decisão' })
        .map((link) => link.getAttribute('href')),
    ).toEqual(['/decisoes/tjdft-jurisdf/2000001', '/decisoes/tjdft-jurisdf/2000002']);
    expect(screen.getByLabelText('3 itens salvos')).toHaveTextContent('3');
    fireEvent.click(drawer().getByRole('button', { name: 'Pesquisas 1' }));
    expect(drawer().getAllByRole('article')).toHaveLength(1);
    expect(drawer().getByRole('article', { name: SEARCH.name })).toBeVisible();
  });

  it('resumes the saved search with fresh results and opens a saved decision using its current detail', async () => {
    const server = api([SEARCH], [savedDecision(SECOND)]);
    renderApp();
    await search();
    openItems();
    fireEvent.click(await drawer().findByRole('button', { name: 'Reabrir pesquisa' }));
    expect(await screen.findByText(`Resultado atualizado 2: ${FIRST.identifier}.`)).toBeVisible();
    expect(currentAddress()).toBe('/');
    expect(screen.getByRole('searchbox')).toHaveValue(String(SEARCH.filters.q));
    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('date');
    const latest = server.requests
      .filter(({ url }) => url.pathname === '/decisions')
      .slice(-1)[0].url;
    expect(latest.searchParams.get('tribunal')).toBe('TJDFT');
    expect(latest.searchParams.get('date_from')).toBe('2026-01-01');
    expect(latest.searchParams.get('page')).toBe('1');
    openItems();
    fireEvent.click(await drawer().findByRole('button', { name: 'Decisões 1' }));
    fireEvent.click(drawer().getByRole('link', { name: 'Abrir decisão' }));
    await waitFor(() => expect(currentAddress()).toBe('/decisoes/tjdft-jurisdf/2000002'));
    expect(
      await within(screen.getByRole('complementary')).findByText(SECOND.summary),
    ).toBeVisible();
    expect(screen.queryByRole('dialog', { name: 'Itens salvos' })).not.toBeInTheDocument();
    expect(
      server.requests.some(({ url }) => url.pathname === '/decisions/tjdft-jurisdf/2000002'),
    ).toBe(true);
  });

  it('deletes only the selected records and keeps the remaining decision saved after remount', async () => {
    const server = api([SEARCH], [savedDecision(FIRST), savedDecision(SECOND)]);
    const view = renderApp('/salvas');
    fireEvent.click(
      await drawer().findByRole('button', { name: `Remover pesquisa ${SEARCH.name}` }),
    );
    await drawer().findByText('Sua primeira pesquisa salva começa aqui');
    fireEvent.click(await drawer().findByRole('button', { name: 'Decisões 2' }));
    const [first] = drawer().getAllByRole('article');
    fireEvent.click(
      within(first).getByRole('button', { name: `Remover decisão ${FIRST.case_number}` }),
    );
    await waitFor(() => expect(drawer().getAllByRole('article')).toHaveLength(1));
    expect(drawer().getByRole('link', { name: 'Abrir decisão' })).toHaveAttribute(
      'href',
      '/decisoes/tjdft-jurisdf/2000002',
    );
    expect(screen.getByLabelText('1 item salvo')).toHaveTextContent('1');
    view.unmount();
    renderApp('/decisoes/tjdft-jurisdf/2000002');
    expect(
      await screen.findByRole('button', { name: 'Remover decisão dos itens salvos' }),
    ).toHaveAttribute('aria-pressed', 'true');
    expect(server.records().searches).toEqual([]);
    expect(server.records().decisions).toEqual([savedDecision(SECOND)]);
    const deleted = server.requests.filter(({ init }) => init.method === 'DELETE');
    expect(deleted.map(({ url }) => url.pathname)).toEqual([
      '/searches/search-1',
      '/saved-decisions/tjdft-jurisdf/2000001',
    ]);
    expectAuthenticated(deleted);
  });

  it('explains how to create the first item in both empty categories and updates after deleting the last decision', async () => {
    api([], [savedDecision(FIRST)]);
    renderApp('/salvas');
    expect(await drawer().findByText('Sua primeira pesquisa salva começa aqui')).toBeVisible();
    expect(drawer().getByText(/Faça uma busca, ajuste os filtros/)).toHaveTextContent(
      'Salvar pesquisa',
    );
    fireEvent.click(await drawer().findByRole('button', { name: 'Decisões 1' }));
    fireEvent.click(drawer().getByRole('button', { name: `Remover decisão ${FIRST.case_number}` }));
    expect(await drawer().findByText('Guarde sua primeira decisão')).toBeVisible();
    expect(drawer().getByText(/Nos resultados ou no detalhe de uma decisão/)).toHaveTextContent(
      'Salvar',
    );
    expect(drawer().getByRole('button', { name: 'Decisões 0' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(drawer().queryByRole('article')).not.toBeInTheDocument();
    expect(screen.getByLabelText('0 itens salvos')).toHaveTextContent('0');
    fireEvent.click(drawer().getByRole('button', { name: 'Pesquisas 0' }));
    expect(drawer().getByText('Sua primeira pesquisa salva começa aqui')).toBeVisible();
  });
});
