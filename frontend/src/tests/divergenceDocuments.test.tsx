import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { Divergence } from '../api/divergence';
import { rememberSession } from '../api/token';
import type { SearchParams } from '../api/search';
import DivergencePanel from '../components/DivergencePanel';
import { selectIndicator } from '../search/indicatorSelection';
import { resetBuffer } from '../search/resultsBuffer';
import { currentAddress, renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const rows = [
  { id: 1, court: 'STJ', panel: 'Turma A', code: 198 },
  { id: 2, court: 'STJ', panel: 'Turma A', code: 198 },
  { id: 3, court: 'STJ', panel: 'Turma B', code: 198 },
  { id: 4, court: 'STJ', panel: 'Turma A', code: 213 },
  { id: 5, court: 'TJDFT', panel: 'Turma A', code: 198 },
];
function decision(row: (typeof rows)[number]) {
  return {
    source: 'fixture',
    identifier: String(row.id),
    court: row.court,
    case_number: `processo-${row.id === 2 ? 1 : row.id}`,
    judging_body: row.panel,
    reporting_judge: `RELATOR ${row.id}`,
    decided_on: '2026-03-10',
    small_claims: false,
    source_url: `https://example.test/${row.id}`,
    source_url_reachable: true,
    source_url_shared: false,
    snippet: `Dano moral. Documento ${row.id}.`,
    class_code: row.code,
    judged_on: '2026-03-10',
    published_on: '2026-03-15',
    summary: `Ementa atual do documento ${row.id}.`,
    outcome: 'negado',
    deliberation: null,
    thesis: [],
    full_text_available: true,
    sections: null,
  };
}
function divergence(): Divergence {
  const groups = new Map<string, typeof rows>();
  for (const row of rows) {
    const key = JSON.stringify([row.court, row.code, row.panel]);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return {
    rule_version: 'RF22-v1',
    documents: rows.length,
    tested_pairs: 0,
    thresholds: {
      minimum_classified_processes: 50,
      minimum_classification_coverage: 0.8,
      minimum_expected_cell: 5,
      alpha: 0.05,
      minimum_effect: 0.15,
    },
    pairs: [],
    panels: [...groups.values()].map((items) => {
      const first = items[0],
        processes = new Set(items.map((row) => decision(row).case_number)).size;
      return {
        court: first.court,
        panel: first.panel,
        class_code: first.code,
        documents: items.length,
        classified_documents: items.length,
        unknown_documents: 0,
        outcomes: { denied: items.length, granted: 0, partially_granted: 0 },
        processes,
        missing_process_documents: 0,
        repeated_documents: items.length - processes,
      };
    }),
  };
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function api(override?: (url: URL) => Response | undefined) {
  const requests: { url: URL; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      requests.push({ url, init });
      const custom = override?.(url);
      if (custom) return custom;
      if (url.pathname === '/saved-decisions') return json({ decisions: [] });
      if (url.pathname === '/courts') return json({ courts: [] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/indicators/divergence') return json(divergence());
      if (url.pathname === '/decisions') {
        const selected = rows.filter(
          (row) =>
            (!url.searchParams.has('tribunal') ||
              url.searchParams.getAll('tribunal').includes(row.court)) &&
            (!url.searchParams.has('orgao_julgador') ||
              url.searchParams.getAll('orgao_julgador').includes(row.panel)) &&
            (!url.searchParams.has('classe_cnj') ||
              url.searchParams.getAll('classe_cnj').includes(String(row.code))),
        );
        return json({
          total: selected.length,
          page: 1,
          page_size: Number(url.searchParams.get('page_size') ?? 12),
          results: selected.map(decision),
        });
      }
      const detail = rows.find((row) => url.pathname === `/decisions/fixture/${row.id}`);
      if (detail) return json(decision(detail));
      if (/\/(doctrine|legislation|related|opposing)$/.test(url.pathname))
        return json({ results: [] });
      return json({});
    }),
  );
  return requests;
}
beforeEach(() => {
  resetBuffer();
  rememberSession('divergence-documents-token');
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
const drawer = () => within(screen.getByRole('dialog'));
const opener = (court = 'STJ', code = 198) =>
  screen.getByRole('button', {
    name: new RegExp(`Consultar decisões da turma Turma A no ${court}, classe CNJ ${code}:`),
  });
async function openPanorama() {
  const user = userEvent.setup();
  renderApp();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'dano moral' } });
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findByRole('button', { name: 'Salvar pesquisa' });
  await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenar por' }), 'date');
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await user.click(
    screen.getByRole('button', { name: 'Como as turmas do mesmo tribunal decidiram' }),
  );
  await waitFor(() => expect(opener()).toBeEnabled());
  return user;
}

it('intersects court, panel and class while retaining every other applied filter and ordering', () => {
  const original: SearchParams = {
    q: '"dano moral"',
    tribunal: ['STJ', 'TJDFT'],
    orgao_julgador: ['Turma A', 'Turma B'],
    classe_cnj: [198, 213],
    relator: ['ANA'],
    resultado: ['negado'],
    orgao_julgador_excluido: ['Turma Z'],
    relator_excluido: ['BRUNO'],
    date_from: '2026-01-01',
    date_to: '2026-12-31',
    published_from: '2026-02-01',
    published_to: '2026-11-30',
    order: 'date',
    page: 7,
  };
  const selection = selectIndicator(
    original,
    { kind: 'divergence', court: 'STJ', panel: 'Turma A', classCode: 198, count: 2 },
    { total: 50, filterCount: 10 },
  );
  expect(selection.params).toEqual({
    ...original,
    tribunal: ['STJ'],
    orgao_julgador: ['Turma A'],
    classe_cnj: [198],
    page: 1,
  });
  expect(selection.original).toEqual({ ...original, page: 1 });
  expect(selection.count).toBe(2);
  expect(selection.originalTotal).toBe(50);
  expect(original.page).toBe(7);
  expect(original.tribunal).toEqual(['STJ', 'TJDFT']);
});

it.each([
  { tribunal: ['TJDFT'] },
  { orgao_julgador: ['Turma B'] },
  { classe_cnj: [213] },
  { orgao_julgador_excluido: ['Turma A'] },
])('cannot widen incompatible original filters: %j', (filters) => {
  expect(
    selectIndicator(
      { q: 'dano moral', ...filters },
      { kind: 'divergence', court: 'STJ', panel: 'Turma A', classCode: 198, count: 2 },
    ).params,
  ).toBeNull();
});

it('opens every document behind the card, including repeated processes, and excludes homonyms in another court or class', async () => {
  const requests = api();
  const user = await openPanorama();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'rascunho não aplicado' } });
  await user.click(opener());
  expect(await drawer().findByText('Dano moral. Documento 1.')).toBeVisible();
  expect(drawer().getByText('Dano moral. Documento 2.')).toBeVisible();
  expect(drawer().getAllByRole('article')).toHaveLength(2);
  expect(drawer().queryByText('Dano moral. Documento 4.')).not.toBeInTheDocument();
  expect(drawer().queryByText('Dano moral. Documento 5.')).not.toBeInTheDocument();
  const request = requests.filter(({ url }) => url.pathname === '/decisions').slice(-1)[0];
  expect(request.url.searchParams.get('q')).toBe('dano moral');
  expect(request.url.searchParams.getAll('tribunal')).toEqual(['STJ']);
  expect(request.url.searchParams.getAll('orgao_julgador')).toEqual(['Turma A']);
  expect(request.url.searchParams.getAll('classe_cnj')).toEqual(['198']);
  expect(request.url.searchParams.get('order')).toBe('date');
  expect(request.url.searchParams.get('page')).toBe('1');
  expect(new Headers(request.init.headers).get('Authorization')).toBe(
    'Bearer divergence-documents-token',
  );
  expect(drawer().getByText('decisões neste indicador')).toBeVisible();
});

it('returns from the detail to the drawer and restores Panorama and keyboard focus on closing', async () => {
  const requests = api();
  const user = await openPanorama();
  const trigger = opener();
  trigger.focus();
  await user.keyboard('{Enter}');
  await drawer().findByText('Dano moral. Documento 2.');
  await user.click(drawer().getAllByRole('button', { name: 'Abrir decisão' })[1]);
  expect(await drawer().findByText('Ementa atual do documento 2.')).toBeVisible();
  expect(currentAddress()).toBe('/');
  await user.click(drawer().getByRole('button', { name: 'Voltar aos documentos do indicador' }));
  expect(drawer().getByText('Dano moral. Documento 2.')).toBeVisible();
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('tab', { name: 'Panorama' })).toHaveAttribute('aria-selected', 'true');
  expect(
    screen.getByRole('button', { name: 'Como as turmas do mesmo tribunal decidiram' }),
  ).toHaveAttribute('aria-expanded', 'true');
  await waitFor(() => expect(trigger).toHaveFocus());
  expect(requests.filter(({ url }) => url.pathname === '/indicators/divergence')).toHaveLength(1);
});

it('browser Back closes one selection and another class can be opened without stale context', async () => {
  const requests = api();
  const user = await openPanorama();
  await user.click(opener());
  await drawer().findByText('Dano moral. Documento 1.');
  fireEvent.click(opener()); // disabled while the drawer is open: no extra history entry
  fireEvent.click(screen.getByTestId('browser-back'));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  await user.click(opener('STJ', 213));
  expect(await drawer().findByText('Dano moral. Documento 4.')).toBeVisible();
  expect(drawer().getAllByRole('article')).toHaveLength(1);
  const last = requests.filter(({ url }) => url.pathname === '/decisions').slice(-1)[0].url;
  expect(last.searchParams.get('classe_cnj')).toBe('213');
});

it('keeps small samples accessible and removal of the indicator selection restores the original search', async () => {
  api();
  const user = await openPanorama();
  const card = within(screen.getByRole('region', { name: 'STJ — Classe CNJ 198' })).getByRole(
    'article',
    { name: 'Turma A — STJ' },
  );
  expect(within(card).getByText(/Volume insuficiente/)).toBeVisible();
  await user.click(opener());
  await drawer().findByText('Dano moral. Documento 1.');
  await user.click(drawer().getByRole('button', { name: /Remover seleção do indicador Turma:/ }));
  expect(await drawer().findByText('Dano moral. Documento 5.')).toBeVisible();
  expect(drawer().getAllByRole('article')).toHaveLength(5);
  expect(drawer().getByText('decisões na pesquisa original')).toBeVisible();
});

it('retries a failed document request with the same panel selection', async () => {
  let failed = true;
  const requests = api((url) =>
    url.pathname === '/decisions' && url.searchParams.has('orgao_julgador') && failed
      ? json({}, 503)
      : undefined,
  );
  const user = await openPanorama();
  await user.click(opener());
  expect(await drawer().findByRole('alert')).toHaveTextContent(
    'Não foi possível carregar os documentos',
  );
  failed = false;
  await user.click(drawer().getByRole('button', { name: 'Tentar novamente' }));
  expect(await drawer().findByText('Dano moral. Documento 2.')).toBeVisible();
  const narrowed = requests.filter(
    ({ url }) => url.pathname === '/decisions' && url.searchParams.has('orgao_julgador'),
  );
  expect(narrowed).toHaveLength(2);
  expect(narrowed[0].url.search).toBe(narrowed[1].url.search);
});

it('does not offer a misleading broad query for a card without class or body identification', () => {
  const data = divergence();
  data.panels[0].class_code = null;
  data.panels[1].panel = null;
  const select = vi.fn();
  render(
    <DivergencePanel
      divergence={{ status: 'loaded', divergence: data }}
      onRetry={() => undefined}
      onSelect={select}
    />,
  );
  expect(screen.getAllByText(/Acesso ao recorte da turma indisponível/)).toHaveLength(2);
  expect(
    screen.queryByRole('button', { name: /turma Turma A no STJ, classe CNJ null/ }),
  ).not.toBeInTheDocument();
  expect(select).not.toHaveBeenCalled();
});
