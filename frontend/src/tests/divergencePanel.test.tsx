import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  readDivergence,
  type Divergence,
  type DivergenceCounts,
  type DivergenceSample,
} from '../api/divergence';
import DivergencePanel from '../components/DivergencePanel';
import { rememberSession } from '../api/token';
import { resetBuffer } from '../search/resultsBuffer';
import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const counts = (denied: number, granted: number, partially_granted: number): DivergenceCounts => ({
  denied,
  granted,
  partially_granted,
});
function sample(panel: string, outcomes: DivergenceCounts): DivergenceSample {
  const total = outcomes.denied + outcomes.granted + outcomes.partially_granted;
  return {
    panel,
    processes: total,
    classified: total,
    unknown: 0,
    coverage: total ? 1 : null,
    outcomes,
    shared_processes_excluded: 0,
    missing_process_documents: 0,
    repeated_documents: 0,
  };
}
function fixture(a = counts(80, 10, 10), b = counts(20, 10, 70)): Divergence {
  const left = sample('Turma A', a),
    right = sample('Turma B', b);
  return {
    rule_version: 'RF22-v1',
    documents: left.processes + right.processes,
    tested_pairs: 1,
    thresholds: {
      minimum_classified_processes: 50,
      minimum_classification_coverage: 0.8,
      minimum_expected_cell: 5,
      alpha: 0.05,
      minimum_effect: 0.15,
    },
    panels: [left, right].map((item) => ({
      court: 'STJ',
      class_code: 198,
      panel: item.panel,
      documents: item.processes,
      classified_documents: item.classified,
      unknown_documents: 0,
      outcomes: item.outcomes,
      processes: item.processes,
      missing_process_documents: 0,
      repeated_documents: 0,
    })),
    pairs: [
      {
        court: 'STJ',
        class_code: 198,
        left,
        right,
        reason: 'difference',
        signal: true,
        raw_p: 2.576757109e-18,
        adjusted_p: 2.576757109e-18,
        effect: 0.6,
      },
    ],
  };
}
const noop = () => undefined;
const show = (divergence = fixture()) =>
  render(<DivergencePanel divergence={{ status: 'loaded', divergence }} onRetry={noop} />);
beforeEach(() => {
  resetBuffer();
  rememberSession('divergence-test-token');
});
afterEach(() => {
  rememberSession(null);
  vi.unstubAllGlobals();
});

it('shows both panels with their own document numbers and a separately labelled process sample', () => {
  show();
  for (const name of ['Turma A', 'Turma B']) {
    const card = within(screen.getByRole('article', { name: `${name} — STJ` }));
    expect(card.getByText('100')).toBeVisible();
    expect(card.getByText(/100 processos identificados/)).toBeVisible();
    expect(card.getByText(/Os resultados acima contam documentos/)).toBeVisible();
  }
  expect(screen.getByText('STJ · Classe CNJ 198')).toBeVisible();
  expect(screen.getByText(/Diferença estatística não comprova divergência jurídica/)).toBeVisible();
  expect(screen.getAllByText(/processos classificados de/)).toHaveLength(2);
  expect(screen.getByText(/p ajustado \(Holm\)/)).toHaveTextContent('60 pontos percentuais');
});

it('highlights only a backend-supported pair and keeps comparable cards neutral', () => {
  const view = show();
  expect(view.container.querySelectorAll('.divergence__pair--signal')).toHaveLength(1);
  expect(view.container.querySelectorAll('.divergence__panel')).toHaveLength(2);
  const data = fixture(counts(60, 20, 20), counts(55, 25, 20));
  Object.assign(data.pairs[0], {
    reason: 'not_significant',
    signal: false,
    raw_p: 0.6794487781,
    adjusted_p: 0.6794487781,
    effect: 0.05,
  });
  view.rerender(
    <DivergencePanel divergence={{ status: 'loaded', divergence: data }} onRetry={noop} />,
  );
  expect(view.container.querySelector('.divergence__pair--signal')).toBeNull();
  expect(screen.getByText(/Sem evidência estatística suficiente/)).toBeVisible();
});

it('does not hide small samples or invent a p-value for them', () => {
  const data = fixture(counts(4, 0, 1), counts(1, 0, 4));
  data.tested_pairs = 0;
  Object.assign(data.pairs[0], {
    reason: 'insufficient_sample',
    signal: false,
    raw_p: null,
    adjusted_p: null,
    effect: null,
  });
  const view = show(data);
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getAllByText('5', { selector: '.divergence__count strong' })).toHaveLength(2);
  expect(screen.getAllByText(/Volume insuficiente/)).toHaveLength(2);
  expect(screen.getByText('Amostra insuficiente para uma conclusão estatística.')).toBeVisible();
  expect(view.container.querySelector('.divergence__pair--signal')).toBeNull();
  expect(screen.queryByText(/p ajustado \(Holm\)/)).not.toBeInTheDocument();
});

it('shows unvalidated competence and missing metadata without declaring equivalence', () => {
  const data = fixture();
  Object.assign(data.pairs[0], {
    reason: 'unvalidated_group',
    signal: false,
    raw_p: null,
    adjusted_p: null,
    effect: null,
  });
  data.panels.push({
    ...data.panels[0],
    panel: null,
    class_code: null,
    documents: 0,
    classified_documents: 0,
    processes: 0,
    outcomes: counts(0, 0, 0),
  });
  const view = show(data);
  expect(screen.getByText(/competência comparável ainda não validada/)).toBeVisible();
  expect(screen.getByText('Órgão julgador não informado')).toBeVisible();
  expect(screen.getByText('STJ · Classe processual não informada')).toBeVisible();
  expect(view.container.querySelector('.divergence__pair--signal')).toBeNull();
});

it('keeps idle, loading, empty and failed states distinct and offers retry', () => {
  const retry = vi.fn();
  const view = render(<DivergencePanel divergence={{ status: 'idle' }} onRetry={retry} />);
  expect(screen.getByText(/Pesquise um tema/)).toBeVisible();
  view.rerender(<DivergencePanel divergence={{ status: 'loading' }} onRetry={retry} />);
  expect(screen.getByRole('status')).toHaveTextContent('Carregando');
  expect(screen.queryByRole('article')).not.toBeInTheDocument();
  view.rerender(
    <DivergencePanel
      divergence={{
        status: 'loaded',
        divergence: { ...fixture(), documents: 0, panels: [], pairs: [], tested_pairs: 0 },
      }}
      onRetry={retry}
    />,
  );
  expect(screen.getByText(/Nenhuma decisão encontrada/)).toBeVisible();
  view.rerender(
    <DivergencePanel
      divergence={{ status: 'failed', message: 'Não foi possível carregar a comparação.' }}
      onRetry={retry}
    />,
  );
  expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível');
  expect(screen.queryByText(/Nenhuma decisão encontrada/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
  expect(retry).toHaveBeenCalledOnce();
});

it('rejects unreadable responses, inconsistent denominators and unsupported signals', () => {
  expect(readDivergence(fixture()).panels).toHaveLength(2);
  expect(() => readDivergence({})).toThrow();
  expect(() => readDivergence({ ...fixture(), documents: null })).toThrow();
  const invalid = fixture();
  invalid.pairs[0].adjusted_p = 0.2;
  expect(() => readDivergence(invalid)).toThrow();
  invalid.pairs[0].adjusted_p = 0.001;
  invalid.pairs[0].left.coverage = 0.79;
  expect(() => readDivergence(invalid)).toThrow();
  expect(() => readDivergence({ ...fixture(), rule_version: 'RF22-unknown' })).toThrow();
});

function api(answer: (url: URL) => Response | Promise<Response>) {
  const requests: { url: URL; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      requests.push({ url, init });
      if (url.pathname === '/indicators/divergence') return answer(url);
      if (url.pathname === '/saved-decisions') return json({ decisions: [] });
      if (url.pathname === '/courts') return json({ courts: [] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/decisions')
        return json({ total: 200, page: 1, page_size: 60, results: [] });
      return json({});
    }),
  );
  return requests;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const dimension = () =>
  screen.getByRole('button', { name: 'Como as turmas do mesmo tribunal decidiram' });
async function search(q = 'dano moral') {
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: q } });
  fireEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findByRole('button', { name: 'Salvar pesquisa' });
}

it('uses the applied cut and authenticated API, caches across dimension changes and retries a failure', async () => {
  let failed = true;
  const requests = api(() => (failed ? json({}, 503) : json(fixture())));
  renderApp();
  await search();
  expect(requests.filter(({ url }) => url.pathname === '/indicators/divergence')).toHaveLength(0);
  fireEvent.click(screen.getByRole('tab', { name: 'Panorama' }));
  fireEvent.click(dimension());
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Não foi possível carregar a comparação',
  );
  const first = requests.find(({ url }) => url.pathname === '/indicators/divergence')!;
  expect(first.url.searchParams.get('q')).toBe('dano moral');
  expect(new Headers(first.init.headers).get('Authorization')).toBe('Bearer divergence-test-token');
  failed = false;
  fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
  expect(await screen.findByRole('article', { name: 'Turma A — STJ' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Onde o tema se concentra' }));
  fireEvent.click(dimension());
  expect(requests.filter(({ url }) => url.pathname === '/indicators/divergence')).toHaveLength(2);
});

it('does not let a late response replace a newer applied search', async () => {
  let finish!: (response: Response) => void;
  const requests = api((url) =>
    url.searchParams.get('q') === 'dano moral'
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : json({ ...fixture(), documents: 0, panels: [], pairs: [], tested_pairs: 0 }),
  );
  renderApp();
  await search();
  fireEvent.click(screen.getByRole('tab', { name: 'Panorama' }));
  fireEvent.click(dimension());
  await waitFor(() => expect(finish).toBeDefined());
  await search('outro tema');
  expect(
    await screen.findByText(/Nenhuma decisão encontrada para os filtros aplicados/),
  ).toBeVisible();
  await act(async () => finish(json(fixture())));
  expect(screen.queryByRole('article', { name: 'Turma A — STJ' })).not.toBeInTheDocument();
  expect(
    requests
      .filter(({ url }) => url.pathname === '/indicators/divergence')
      .map(({ url }) => url.searchParams.get('q')),
  ).toEqual(['dano moral', 'outro tema']);
});
