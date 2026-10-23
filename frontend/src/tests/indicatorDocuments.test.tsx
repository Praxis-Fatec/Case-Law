import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderApp } from './renderApp';
import { selectIndicator } from '../search/indicatorSelection';
import TimelineChart from '../components/TimelineChart';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
// Keep the real lazy renderer in this integration test.
void TimelineChart;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const decision = (n: number) => ({
  source: 'teste',
  identifier: String(n),
  court: 'STJ',
  case_number: `processo-${n}`,
  judging_body: 'CORTE ESPECIAL',
  reporting_judge: 'RELATOR A',
  decided_on: '2024-05-20',
  small_claims: null,
  source_url: 'https://example.test/decision',
  source_url_reachable: true,
  deliberation: null,
  snippet: 'Dano <mark>moral</mark> comprovado.',
});
function api(answer?: (url: URL) => Response | Promise<Response>) {
  const requests: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requests.push(url);
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'Superior Tribunal de Justiça' }] });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/indicators/last-update')
        return json({ state: 'loaded', updated_at: '2026-10-22T12:00:00Z' });
      if (url.pathname === '/indicators/volume-by-court')
        return json({
          total: 10,
          courts: [{ abbreviation: 'STJ', name: 'Superior Tribunal de Justiça', decisions: 7 }],
        });
      if (url.pathname === '/indicators/outcome-share')
        return json({
          total: 10,
          classified: 10,
          unclassified: 0,
          outcomes: [
            { outcome: 'provido', decisions: 4, share: 40 },
            { outcome: 'negado', decisions: 6, share: 60 },
            { outcome: 'parcialmente_provido', decisions: 0, share: 0 },
          ],
        });
      if (url.pathname === '/indicators/volume-by-period')
        return json({
          total: 10,
          granularity: 'quarter',
          periods: [
            { period: '2024-01-01', decisions: 3 },
            { period: '2024-04-01', decisions: 7 },
          ],
        });
      if (url.pathname === '/decisions') {
        if (
          url.searchParams.has('tribunal') ||
          url.searchParams.has('resultado') ||
          url.searchParams.has('date_to')
        ) {
          if (answer) return answer(url);
          const total =
            url.searchParams.get('resultado') === 'parcialmente_provido'
              ? 0
              : url.searchParams.has('resultado')
                ? 4
                : 7;
          const page = Number(url.searchParams.get('page') ?? 1);
          const size = Number(url.searchParams.get('page_size') ?? 6);
          return json({
            total,
            page,
            page_size: size,
            results: Array.from(
              { length: Math.max(0, Math.min(size, total - (page - 1) * size)) },
              (_, n) => decision((page - 1) * size + n + 1),
            ),
          });
        }
        return json({ total: 1, page: 1, page_size: 6, results: [decision(0)] });
      }
      return json({
        ...decision(1),
        class_code: 198,
        judged_on: '2024-05-20',
        published_on: null,
        summary: 'Texto da decisão selecionada.',
        outcome: 'provido',
        full_text_available: false,
        sections: null,
      });
    }),
  );
  return requests;
}
beforeEach(() => {
  // jsdom does not implement the native dialog API. Focus trapping and Escape
  // are also checked in the real browser, where showModal makes the page inert.
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: {
      configurable: true,
      value(this: HTMLDialogElement) {
        this.setAttribute('open', '');
      },
    },
    close: {
      configurable: true,
      value(this: HTMLDialogElement) {
        this.removeAttribute('open');
      },
    },
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
async function panorama() {
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await screen.findByRole('button', { name: /Consultar documentos de STJ/ });
  return user;
}
const lastSearch = (requests: URL[]) => {
  const searches = requests.filter((u) => u.pathname === '/decisions');
  return searches[searches.length - 1];
};

it('opens court documents by keyboard, paginates, reads a decision and restores the Panorama and focus', async () => {
  const requests = api();
  const user = await panorama();
  const target = screen.getByRole('button', { name: /Consultar documentos de STJ/ });
  target.focus();
  await user.keyboard('{Enter}');
  const drawer = await screen.findByRole('dialog', { name: 'STJ: 7 decisões' });
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.get('q')).toBe(
    'prescrição intercorrente em execução fiscal',
  );
  expect(lastSearch(requests).searchParams.getAll('tribunal')).toEqual(['STJ']);
  await user.click(within(drawer).getByRole('button', { name: 'Próxima' }));
  await waitFor(() =>
    expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(1),
  );
  expect(lastSearch(requests).searchParams.get('page')).toBe('2');
  await user.click(within(drawer).getByRole('button', { name: 'Abrir decisão' }));
  await within(drawer).findByText('Texto da decisão selecionada.');
  await user.click(
    within(drawer).getByRole('button', { name: 'Voltar aos documentos do indicador' }),
  );
  expect(within(drawer).getAllByRole('button', { name: 'Abrir decisão' })).toHaveLength(1);
  const count = requests.length;
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(target).toHaveFocus();
  expect(screen.getByRole('tab', { name: 'Panorama' })).toHaveAttribute('aria-selected', 'true');
  expect(requests).toHaveLength(count);
});
it('selects a result without dropping the expression and handles an empty category', async () => {
  const requests = api();
  const user = await panorama();
  await user.click(
    await screen.findByRole('button', { name: /Consultar documentos com resultado Provido:/ }),
  );
  let drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.getAll('resultado')).toEqual(['provido']);
  fireEvent(drawer, new Event('cancel', { bubbles: true, cancelable: true }));
  await user.click(
    screen.getByRole('button', {
      name: /Consultar documentos com resultado Parcialmente provido:/,
    }),
  );
  drawer = screen.getByRole('dialog');
  expect(await within(drawer).findByText(/Nenhum documento encontrado/)).toBeInTheDocument();
});
it('uses the declared quarter for period bounds and has no interactive target inside aria-hidden', async () => {
  const requests = api();
  const user = await panorama();
  await user.click(await screen.findByText('Consultar documentos por período'));
  const target = await screen.findByRole('button', { name: /Consultar documentos de 2T\/2024/ });
  expect(target.closest('[aria-hidden="true"]')).toBeNull();
  await user.click(target);
  const drawer = screen.getByRole('dialog');
  await within(drawer).findAllByRole('button', { name: 'Abrir decisão' });
  expect(lastSearch(requests).searchParams.get('date_from')).toBe('2024-04-01');
  expect(lastSearch(requests).searchParams.get('date_to')).toBe('2024-06-30');
  for (const button of document.querySelectorAll('.indicator-target'))
    expect(button.closest('[aria-hidden="true"]')).toBeNull();
});
it('disables the targets during loading, allows retry and discards a late response after closing', async () => {
  let resolve!: (response: Response) => void;
  let calls = 0;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  api(() => (++calls === 1 ? json({}, 503) : pending));
  const user = await panorama();
  await user.click(screen.getByRole('button', { name: /Consultar documentos de STJ/ }));
  const drawer = screen.getByRole('dialog');
  await within(drawer).findByRole('alert');
  await user.click(within(drawer).getByRole('button', { name: 'Tentar novamente' }));
  expect(within(drawer).getByRole('status')).toHaveTextContent('Carregando documentos');
  expect(screen.getByRole('button', { name: /Consultar documentos de STJ/ })).toBeDisabled();
  await user.click(
    within(drawer).getByRole('button', { name: 'Fechar documentos e voltar ao Panorama' }),
  );
  await act(async () => resolve(json({ total: 7, page: 1, page_size: 6, results: [decision(1)] })));
  expect(screen.queryByRole('dialog')).toBeNull();
});
it.each([
  ['month', '2024-02-01', '2024-02-01', '2024-02-29'],
  ['quarter', '2024-04-01', '2024-04-01', '2024-06-30'],
  ['year', '2024-01-01', '2024-01-01', '2024-12-31'],
] as const)(
  'adds a %s period to every original filter with inclusive bounds',
  (granularity, period, from, to) => {
    const original = {
      q: 'dano moral',
      tribunal: ['STJ', 'TJDFT'],
      orgao_julgador: ['CORTE'],
      relator: ['RELATOR A'],
      classe_cnj: [198],
      published_from: '2024-02-10',
      order: 'date' as const,
      page: 4,
    };
    const selected = selectIndicator(original, { kind: 'period', granularity, period, count: 2 });
    expect(selected.params).toEqual({ ...original, page: 1, date_from: from, date_to: to });
    expect(original.page).toBe(4);
  },
);
it('intersects original bounds and never turns incompatible selections into an unrestricted search', () => {
  expect(
    selectIndicator(
      { q: 'dano moral', date_from: '2024-05-10', date_to: '2024-05-20' },
      { kind: 'period', period: '2024-01-01', granularity: 'year', count: 2 },
    ).params,
  ).toMatchObject({ date_from: '2024-05-10', date_to: '2024-05-20' });
  expect(
    selectIndicator(
      { q: 'dano moral', tribunal: ['STJ'] },
      { kind: 'court', court: 'TJDFT', count: 0 },
    ).params,
  ).toBeNull();
  expect(
    selectIndicator(
      { q: 'dano moral', resultado: ['negado'] },
      { kind: 'outcome', outcome: 'provido', count: 0 },
    ).params,
  ).toBeNull();
});
