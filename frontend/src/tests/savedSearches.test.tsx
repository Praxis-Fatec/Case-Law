import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderApp, currentAddress } from './renderApp';
import { resetBuffer } from '../search/resultsBuffer';
import { rememberSession } from '../api/token';
import { resumeSavedSearch } from '../search/savedSearches';
import { savedSearchParams, type SavedSearch } from '../api/savedSearches';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const saved: SavedSearch = {
  id: 'search-1',
  name: 'Execução fiscal',
  created_at: '2026-11-15T20:53:00Z',
  filters: {
    q: '"prescrição intercorrente"',
    tribunal: ['STJ', 'TJDFT'],
    orgao_julgador: ['TURMA A'],
    relator: ['ANA'],
    classe_cnj: [198],
    date_from: '2022-01-01',
    date_to: '2026-09-05',
    published_from: '2023-01-01',
    published_to: '2026-10-01',
    order: 'date',
  },
};

function api(
  initial: SavedSearch[] = [],
  override?: (url: URL, init: RequestInit) => Response | Promise<Response> | undefined,
) {
  let records = [...initial];
  const requests: { url: URL; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      requests.push({ url, init });
      const custom = override?.(url, init);
      if (custom) return custom;
      if (url.pathname === '/saved-decisions') return json({ decisions: [] });
      if (url.pathname === '/courts')
        return json({
          courts: ['STJ', 'TJDFT'].map((abbreviation) => ({ abbreviation, name: abbreviation })),
        });
      if (url.pathname === '/filters')
        return json({
          judging_bodies: [{ value: 'TURMA A', label: 'TURMA A' }],
          reporting_judges: [{ value: 'ANA', label: 'ANA' }],
          procedural_classes: [{ value: 198, label: 'Apelação' }],
        });
      if (url.pathname === '/decisions')
        return json({ total: 1, page: 1, page_size: 6, results: [] });
      if (url.pathname === '/searches' && init.method === 'POST') {
        const body = JSON.parse(String(init.body));
        const item = { id: `search-${records.length + 1}`, created_at: saved.created_at, ...body };
        records = [item, ...records];
        return json(item, 201);
      }
      if (url.pathname === '/searches') return json({ searches: records });
      if (url.pathname.startsWith('/searches/')) {
        const id = decodeURIComponent(url.pathname.split('/').pop()!);
        const item = records.find((record) => record.id === id);
        if (!item) return json({ detail: 'Not found' }, 404);
        if (init.method === 'DELETE') {
          records = records.filter((record) => record.id !== id);
          return new Response(null, { status: 204 });
        }
        return json(item);
      }
      if (url.pathname === '/indicators/coverage')
        return json({ documents: 0, courts: [], state: 'never_loaded' });
      return json({});
    }),
  );
  return requests;
}
const openItems = () => fireEvent.click(screen.getByRole('link', { name: /Itens salvos/ }));
const items = () => screen.getByRole('dialog', { name: 'Itens salvos' });
async function search() {
  fireEvent.change(screen.getByRole('searchbox', { name: 'Pesquisar decisões' }), {
    target: { value: 'dano moral' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Salvar pesquisa/ })).toBeEnabled(),
  );
}
async function openSave(name = 'Minha pesquisa') {
  fireEvent.click(screen.getByRole('button', { name: /Salvar pesquisa/ }));
  const dialog = screen.getByRole('dialog', { name: 'Salvar pesquisa' });
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Nome da pesquisa' }), {
    target: { value: name },
  });
  return dialog;
}
beforeEach(() => {
  resetBuffer();
  rememberSession('saved-search-test-token');
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

it('saves a named applied search without drafts or pagination, then shows it in the drawer', async () => {
  const requests = api([saved]);
  renderApp();
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  await waitFor(() => expect(currentAddress()).toBe('/'));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Salvar pesquisa/ })).toBeEnabled(),
  );
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'rascunho não aplicado' } });
  const dialog = await openSave('  Minha pesquisa  ');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Salvar pesquisa' }));
  expect(await screen.findByRole('button', { name: /Pesquisa salva/ })).toBeVisible();
  const post = requests.find(
    ({ url, init }) => url.pathname === '/searches' && init.method === 'POST',
  )!;
  expect(JSON.parse(String(post.init.body))).toEqual({
    name: 'Minha pesquisa',
    filters: saved.filters,
  });
  expect(new Headers(post.init.headers).get('Authorization')).toBe(
    'Bearer saved-search-test-token',
  );
  expect(JSON.parse(String(post.init.body)).filters).not.toHaveProperty('page');
  openItems();
  expect(await within(items()).findByRole('article', { name: 'Minha pesquisa' })).toBeVisible();
  expect(within(items()).getAllByRole('article')).toHaveLength(2);
});

it('restores expression, every filter and ordering, then fetches current results on page one', async () => {
  const requests = api([saved]);
  renderApp('/cobertura');
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  await waitFor(() => expect(currentAddress()).toBe('/'));
  await waitFor(() =>
    expect(screen.getByRole('combobox', { name: 'Ordenar por' })).toHaveValue('date'),
  );
  expect(screen.getByRole('searchbox')).toHaveValue(String(saved.filters.q));
  const request = requests.find(({ url }) => url.pathname === '/decisions')!.url;
  for (const [key, value] of Object.entries(saved.filters)) {
    expect(request.searchParams.getAll(key)).toEqual(
      Array.isArray(value) ? value.map(String) : [value],
    );
  }
  expect(request.searchParams.get('page')).toBe('1');
  fireEvent.click(screen.getByRole('button', { name: /Filtros/ }));
  expect(await screen.findByRole('checkbox', { name: /STJ/ })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: /TJDFT/ })).toBeChecked();
  expect(document.getElementById('search-filters-judged-from')).toHaveValue('2022-01-01');
  expect(document.getElementById('search-filters-judged-to')).toHaveValue('2026-09-05');
  expect(document.getElementById('search-filters-published-from')).toHaveValue('2023-01-01');
  expect(document.getElementById('search-filters-published-to')).toHaveValue('2026-10-01');
});

it('refetches an identical search instead of resuming a cached result snapshot', async () => {
  const requests = api([{ ...saved, filters: { q: 'dano moral', order: 'relevance' } }]);
  renderApp();
  await search();
  expect(requests.filter(({ url }) => url.pathname === '/decisions')).toHaveLength(1);
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  await waitFor(() =>
    expect(requests.filter(({ url }) => url.pathname === '/decisions')).toHaveLength(2),
  );
  expect(currentAddress()).toBe('/');
});

it('restores outcome and exclusion filters and lets the reader remove them explicitly', async () => {
  const requests = api([
    {
      ...saved,
      filters: {
        ...saved.filters,
        resultado: ['negado'],
        orgao_julgador_excluido: ['TURMA B'],
        relator_excluido: ['BRUNO'],
      },
    },
  ]);
  renderApp();
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  await waitFor(() => expect(currentAddress()).toBe('/'));
  const request = requests.find(({ url }) => url.pathname === '/decisions')!.url;
  expect(request.searchParams.getAll('resultado')).toEqual(['negado']);
  expect(request.searchParams.getAll('orgao_julgador_excluido')).toEqual(['TURMA B']);
  expect(request.searchParams.getAll('relator_excluido')).toEqual(['BRUNO']);
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Remover filtro Resultado: Negado' })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Remover filtro Resultado: Negado' }));
  await waitFor(() =>
    expect(requests.filter(({ url }) => url.pathname === '/decisions')).toHaveLength(2),
  );
  const latest = requests.filter(({ url }) => url.pathname === '/decisions').slice(-1)[0].url;
  expect(latest.searchParams.has('resultado')).toBe(false);
  expect(latest.searchParams.get('relator_excluido')).toBe('BRUNO');
});

it('explains how to create the first saved search and restores header focus on close', async () => {
  api();
  renderApp();
  openItems();
  expect(await within(items()).findByText('Sua primeira pesquisa salva começa aqui')).toBeVisible();
  expect(within(items()).getByText(/Faça uma busca, ajuste os filtros/)).toBeVisible();
  fireEvent.click(within(items()).getByRole('button', { name: 'Voltar à pesquisa' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Itens salvos/ })).toHaveFocus();
});

it('shows a retryable list failure without pretending it is an empty list', async () => {
  let failed = true;
  api([saved], (url) => (url.pathname === '/searches' && failed ? json({}, 503) : undefined));
  renderApp();
  openItems();
  expect(await within(items()).findByRole('alert')).toHaveTextContent(/Não foi possível/);
  expect(
    within(items()).queryByText('Sua primeira pesquisa salva começa aqui'),
  ).not.toBeInTheDocument();
  failed = false;
  fireEvent.click(within(items()).getByRole('button', { name: 'Tentar novamente' }));
  expect(await within(items()).findByRole('article', { name: saved.name })).toBeVisible();
});

it('retains the name after a failed save and allows a retry', async () => {
  let failed = true;
  api([], (url, init) =>
    url.pathname === '/searches' && init.method === 'POST' && failed ? json({}, 503) : undefined,
  );
  renderApp();
  await search();
  const dialog = await openSave('Importante');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Salvar pesquisa' }));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(/Não foi possível/);
  expect(within(dialog).getByRole('textbox')).toHaveValue('Importante');
  failed = false;
  fireEvent.click(within(dialog).getByRole('button', { name: 'Salvar pesquisa' }));
  expect(await screen.findByRole('button', { name: /Pesquisa salva/ })).toBeVisible();
});

it('does not send a blank name or duplicate an in-flight save', async () => {
  let complete: ((response: Response) => void) | undefined;
  const requests = api([], (url, init) =>
    url.pathname === '/searches' && init.method === 'POST'
      ? new Promise<Response>((resolve) => {
          complete = resolve;
        })
      : undefined,
  );
  renderApp();
  await search();
  const dialog = await openSave('   ');
  const submit = within(dialog).getByRole('button', { name: 'Salvar pesquisa' });
  fireEvent.click(submit);
  expect(within(dialog).getByRole('alert')).toHaveTextContent('Informe um nome');
  expect(requests.filter(({ init }) => init.method === 'POST')).toHaveLength(0);
  fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'Nome válido' } });
  fireEvent.submit(submit.closest('form')!);
  fireEvent.submit(submit.closest('form')!);
  await waitFor(() => expect(complete).toBeDefined());
  expect(requests.filter(({ init }) => init.method === 'POST')).toHaveLength(1);
  await act(async () => complete!(json({ ...saved, name: 'Nome válido' }, 201)));
  expect(screen.getByRole('button', { name: /Pesquisa salva/ })).toBeVisible();
});

it('removes a saved search and resets the current save button after confirmed deletion', async () => {
  api();
  renderApp();
  await search();
  const dialog = await openSave('Remover depois');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Salvar pesquisa' }));
  await screen.findByRole('button', { name: /Pesquisa salva/ });
  openItems();
  fireEvent.click(
    await within(items()).findByRole('button', { name: 'Remover pesquisa Remover depois' }),
  );
  expect(await within(items()).findByText('Sua primeira pesquisa salva começa aqui')).toBeVisible();
  fireEvent.click(within(items()).getByRole('button', { name: 'Fechar itens salvos' }));
  expect(screen.getByRole('button', { name: /Salvar pesquisa/ })).toHaveAttribute(
    'aria-disabled',
    'false',
  );
});

it('keeps a card on delete failure and offers another attempt', async () => {
  let failed = true;
  api([saved], (_, init) => (init.method === 'DELETE' && failed ? json({}, 503) : undefined));
  renderApp();
  openItems();
  fireEvent.click(
    await within(items()).findByRole('button', { name: `Remover pesquisa ${saved.name}` }),
  );
  expect(await within(items()).findByRole('alert')).toHaveTextContent(/Não foi possível/);
  expect(within(items()).getByRole('article', { name: saved.name })).toBeVisible();
  failed = false;
  fireEvent.click(within(items()).getByRole('button', { name: `Remover pesquisa ${saved.name}` }));
  expect(await within(items()).findByText('Sua primeira pesquisa salva começa aqui')).toBeVisible();
});

it('handles a search deleted elsewhere without executing a stale search', async () => {
  const requests = api([saved], (url) =>
    url.pathname === '/searches/search-1' ? json({}, 404) : undefined,
  );
  renderApp();
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  expect(await within(items()).findByRole('alert')).toHaveTextContent('não está mais disponível');
  expect(within(items()).queryByRole('article')).not.toBeInTheDocument();
  expect(requests.filter(({ url }) => url.pathname === '/decisions')).toHaveLength(0);
});

it('does not silently discard unknown filters when resuming an incompatible search', async () => {
  const requests = api([{ ...saved, filters: { ...saved.filters, new_filter: ['x'] } }]);
  renderApp();
  openItems();
  fireEvent.click(await within(items()).findByRole('button', { name: 'Reabrir pesquisa' }));
  expect(await within(items()).findByRole('alert')).toHaveTextContent('filtros incompatíveis');
  expect(requests.filter(({ url }) => url.pathname === '/decisions')).toHaveLength(0);
});

it('strips navigation-only fields while saving and validates restored dates', () => {
  expect(
    savedSearchParams({ q: 'dano', page: 5, page_size: 60, highlight: 'resultado', order: 'date' }),
  ).toEqual({ q: 'dano', order: 'date' });
  expect(resumeSavedSearch({ ...saved, filters: { ...saved.filters, page: 9 } }).page).toBe(1);
  expect(() =>
    resumeSavedSearch({ ...saved, filters: { q: 'dano', date_from: '2026-02-30' } }),
  ).toThrow();
  expect(() =>
    resumeSavedSearch({
      ...saved,
      filters: { q: 'dano', date_from: '2026-02-02', date_to: '2026-02-01' },
    }),
  ).toThrow();
});
