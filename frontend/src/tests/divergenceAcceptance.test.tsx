import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Divergence, DivergenceCounts, DivergenceSample } from '../api/divergence';
import { rememberSession } from '../api/token';
import { resetBuffer } from '../search/resultsBuffer';
import { currentAddress, renderApp } from './renderApp';

// These acceptance tests mount the routes, request parser, Panorama and shared
// drawer together. API helpers and component callbacks are never mocked.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
type Counts = [number, number, number];
const json = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
function installApi(small = false) {
  const distributions: [Counts, Counts] = small
    ? [
        [4, 0, 1],
        [1, 0, 4],
      ]
    : [
        [80, 10, 10],
        [20, 10, 70],
      ];
  const documents = distributions.flatMap((counts, index) => {
    let offset = 0;
    return counts.flatMap((count, outcome) =>
      Array.from({ length: count }, () => {
        const identifier = `${index === 0 ? 'A' : 'B'}-${++offset}`;
        return {
          source: 'acceptance-fixture',
          identifier,
          court: 'STJ',
          case_number: `processo-${identifier}`,
          judging_body: `Turma ${index === 0 ? 'A' : 'B'}`,
          reporting_judge: 'RELATOR DE TESTE',
          decided_on: '2026-03-10',
          small_claims: false,
          source_url: `https://example.test/${identifier}`,
          source_url_reachable: true,
          source_url_shared: false,
          class_code: 198,
          judged_on: '2026-03-10',
          published_on: '2026-03-15',
          snippet: `Dano moral. Documento ${identifier}.`,
          summary: `Texto da decisão ${identifier}.`,
          outcome: ['negado', 'provido', 'parcialmente_provido'][outcome],
          deliberation: null,
          thesis: [],
          full_text_available: true,
          sections: null,
        };
      }),
    );
  });
  const samples = distributions.map((values, index): DivergenceSample => {
    const outcomes: DivergenceCounts = {
      denied: values[0],
      granted: values[1],
      partially_granted: values[2],
    };
    const total = values.reduce((sum, n) => sum + n, 0);
    return {
      panel: `Turma ${index === 0 ? 'A' : 'B'}`,
      processes: total,
      classified: total,
      unknown: 0,
      coverage: 1,
      outcomes,
      shared_processes_excluded: 0,
      missing_process_documents: 0,
      repeated_documents: 0,
    };
  });
  // Synthetic approved-pair response: no production competence approval is
  // asserted by the fixture. The backend validates that prerequisite separately.
  const divergence: Divergence = {
    rule_version: 'RF22-v1',
    documents: documents.length,
    tested_pairs: small ? 0 : 1,
    thresholds: {
      minimum_classified_processes: 50,
      minimum_classification_coverage: 0.8,
      minimum_expected_cell: 5,
      alpha: 0.05,
      minimum_effect: 0.15,
    },
    panels: samples.map((sample) => ({
      court: 'STJ',
      class_code: 198,
      panel: sample.panel,
      documents: sample.processes,
      classified_documents: sample.classified,
      unknown_documents: 0,
      outcomes: sample.outcomes,
      processes: sample.processes,
      missing_process_documents: 0,
      repeated_documents: 0,
    })),
    pairs: [
      {
        court: 'STJ',
        class_code: 198,
        left: samples[0],
        right: samples[1],
        signal: !small,
        reason: small ? 'insufficient_sample' : 'difference',
        raw_p: small ? null : 2.576757109e-18,
        adjusted_p: small ? null : 2.576757109e-18,
        effect: small ? null : 0.6,
      },
    ],
  };
  const requests: { url: URL; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = new URL(String(input));
      requests.push({ url, init });
      if (url.pathname === '/saved-decisions') return json({ decisions: [] });
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' }] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/indicators/divergence') return json(divergence);
      if (url.pathname === '/decisions') {
        const selected = documents.filter(
          (row) =>
            (!url.searchParams.has('tribunal') ||
              url.searchParams.getAll('tribunal').includes(row.court)) &&
            (!url.searchParams.has('orgao_julgador') ||
              url.searchParams.getAll('orgao_julgador').includes(row.judging_body)) &&
            (!url.searchParams.has('classe_cnj') ||
              url.searchParams.getAll('classe_cnj').includes(String(row.class_code))),
        );
        const page = Number(url.searchParams.get('page') ?? 1),
          size = Number(url.searchParams.get('page_size') ?? 6);
        return json({
          total: selected.length,
          page,
          page_size: size,
          results: selected.slice((page - 1) * size, page * size),
        });
      }
      const found = documents.find(
        (row) => url.pathname === `/decisions/${row.source}/${row.identifier}`,
      );
      if (found) return json(found);
      if (/\/(doctrine|legislation|related|opposing)$/.test(url.pathname))
        return json({ results: [] });
      // Other Panorama dimensions are outside this acceptance suite.
      return json({});
    }),
  );
  return requests;
}
const panel = () =>
  within(screen.getByRole('region', { name: 'Como as turmas do mesmo tribunal decidiram' }));
const opener = (name: string) =>
  panel().getByRole('button', {
    name: new RegExp(`Consultar decisões da turma ${name} no STJ, classe CNJ 198:`),
  });
async function openPanorama() {
  const user = userEvent.setup();
  renderApp();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'dano moral' } });
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await screen.findByRole('button', { name: 'Salvar pesquisa' });
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await user.click(
    screen.getByRole('button', { name: 'Como as turmas do mesmo tribunal decidiram' }),
  );
  await waitFor(() => expect(opener('Turma A')).toBeEnabled());
  return user;
}
beforeEach(() => {
  resetBuffer();
  rememberSession('divergence-acceptance-token');
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

describe('SCRUM-285 — panel-divergence acceptance', () => {
  it('shows a sustained statistical difference from the authenticated endpoint with its numbers and limitation', async () => {
    const requests = installApi();
    await openPanorama();
    const finding = panel()
      .getByText('Diferença estatística na distribuição dos resultados')
      .closest('details')!;
    expect(finding).toHaveClass('divergence__pair--signal');
    expect(finding).toHaveAttribute('open');
    expect(panel().getAllByRole('article')).toHaveLength(2);
    for (const name of ['Turma A', 'Turma B']) {
      const card = within(panel().getByRole('article', { name: `${name} — STJ` }));
      expect(card.getByText('100', { selector: '.divergence__count strong' })).toBeVisible();
      expect(opener(name)).toBeEnabled();
    }
    expect(within(finding).getByText(/p ajustado \(Holm\)/)).toHaveTextContent(
      '60 pontos percentuais',
    );
    expect(
      panel().getByText(/Diferença estatística não comprova divergência jurídica/),
    ).toBeVisible();
    const request = requests.find(({ url }) => url.pathname === '/indicators/divergence')!;
    expect(request.url.searchParams.get('q')).toBe('dano moral');
    expect(new Headers(request.init.headers).get('Authorization')).toBe(
      'Bearer divergence-acceptance-token',
    );
  });

  it('keeps both insufficient-volume panels visible and readable without a signal or p-value', async () => {
    installApi(true);
    await openPanorama();
    expect(panel().getAllByRole('article')).toHaveLength(2);
    expect(panel().getAllByText('5', { selector: '.divergence__count strong' })).toHaveLength(2);
    expect(panel().getAllByText(/Volume insuficiente/)).toHaveLength(2);
    const explanation = panel().getByText('Amostra insuficiente para uma conclusão estatística.');
    expect(explanation).toBeVisible();
    expect(explanation.closest('details')).not.toHaveClass('divergence__pair--signal');
    expect(
      panel().queryByText('Diferença estatística na distribuição dos resultados'),
    ).not.toBeInTheDocument();
    expect(panel().queryByText(/p ajustado \(Holm\)/)).not.toBeInTheDocument();
    expect(opener('Turma A')).toBeEnabled();
    expect(opener('Turma B')).toBeEnabled();
  });

  it('opens the decisions of a highlighted pair and preserves the return through detail, list and Panorama', async () => {
    const requests = installApi();
    const user = await openPanorama();
    const trigger = opener('Turma B');
    await user.click(trigger);
    const drawer = within(screen.getByRole('dialog'));
    expect(await drawer.findByText('Dano moral. Documento B-1.')).toBeVisible();
    expect(drawer.queryByText('Dano moral. Documento A-1.')).not.toBeInTheDocument();
    expect(drawer.getByRole('heading', { level: 2 })).toHaveTextContent(
      'Turma B · STJ · Classe CNJ 198: 100 decisões',
    );
    const narrowed = requests.find(
      ({ url }) =>
        url.pathname === '/decisions' && url.searchParams.get('orgao_julgador') === 'Turma B',
    )!.url;
    expect(narrowed.searchParams.get('q')).toBe('dano moral');
    expect(narrowed.searchParams.getAll('tribunal')).toEqual(['STJ']);
    expect(narrowed.searchParams.getAll('classe_cnj')).toEqual(['198']);
    await user.click(drawer.getAllByRole('button', { name: 'Abrir decisão' })[0]);
    expect(await drawer.findByText('Texto da decisão B-1.')).toBeVisible();
    await user.click(drawer.getByRole('button', { name: 'Voltar aos documentos do indicador' }));
    expect(drawer.getByText('Dano moral. Documento B-1.')).toBeVisible();
    await user.click(drawer.getByRole('button', { name: 'Voltar ao Panorama' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(currentAddress()).toBe('/');
    expect(screen.getByRole('tab', { name: 'Panorama' })).toHaveAttribute('aria-selected', 'true');
    expect(panel().getByText('Diferença estatística na distribuição dos resultados')).toBeVisible();
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(requests.filter(({ url }) => url.pathname === '/indicators/divergence')).toHaveLength(1);
  });
});
