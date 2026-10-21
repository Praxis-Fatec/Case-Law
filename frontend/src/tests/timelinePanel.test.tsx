import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { renderApp } from './renderApp';
// Preload the real renderer so cold dynamic-import compilation is outside
// the DOM assertion timeout. The production component remains lazy-loaded.
import TimelineChart from '../components/TimelineChart';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const series = (decisions = 12) => ({
  total: decisions,
  granularity: 'month',
  periods: [{ period: '2026-03-01', decisions }],
});
function api(answer: (url: URL) => Response | Promise<Response> = () => json(series())) {
  const requested: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requested.push(url);
      if (url.pathname === '/courts')
        return json({ courts: [{ abbreviation: 'STJ', name: 'STJ' }] });
      if (url.pathname === '/indicators/volume-by-period') return answer(url);
      if (url.pathname === '/decisions')
        return json({ total: 12, page: 1, page_size: 12, results: [] });
      if (url.pathname === '/indicators/volume-by-court') return json({ total: 12, courts: [] });
      if (url.pathname === '/indicators/outcome-share')
        return json({ total: 12, classified: 0, unclassified: 12, outcomes: [] });
      return json({ state: 'loaded', updated_at: '2026-10-20T12:00:00Z' });
    }),
  );
  return () => requested.filter((url) => url.pathname === '/indicators/volume-by-period');
}
afterEach(() => vi.unstubAllGlobals());
it.each([
  ['month', 'Mar/26'],
  ['quarter', '1T/2026'],
  ['year', '2026'],
] as const)('formats %s periods in the accessible table', (granularity, label) => {
  render(
    <TimelineChart
      periods={[{ period: '2026-03-01', decisions: 12 }]}
      granularity={granularity}
      showValues={false}
    />,
  );
  expect(within(screen.getByRole('table')).getByText(label)).toBeInTheDocument();
});

it('distinguishes zero from an unknown count', () => {
  render(
    <TimelineChart
      periods={[
        { period: '2026-01-01', decisions: 0 },
        { period: '2026-02-01', decisions: null },
      ]}
      showValues={false}
    />,
  );
  const table = within(screen.getByRole('table'));
  expect(table.getByText('0')).toBeInTheDocument();
  expect(table.getByText('Não informado')).toBeInTheDocument();
});

const card = () => within(screen.getByRole('article', { name: 'Volume ao longo do tempo' }));

it('loads the applied search in Panorama, including court and dates, only once per cut', async () => {
  const requests = api();
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: /Filtros/ }));
  await user.click(await screen.findByRole('checkbox', { name: /^STJ/ }));
  fireEvent.change(
    within(screen.getByRole('group', { name: 'Data de julgamento' })).getByLabelText('De'),
    { target: { value: '2026-03-01' } },
  );
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  expect(requests()).toHaveLength(0);
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await card().findByRole('table');
  expect(within(card().getByRole('table')).getByText('12')).toBeInTheDocument();
  expect(card().getByRole('table').parentElement).toHaveClass('sr-only');
  expect(card().queryByText('Consultar valores por período')).toBeNull();
  expect(card().queryByText(/Agrupamento pela data/)).toBeNull();
  expect(requests()[0].searchParams.getAll('tribunal')).toEqual(['STJ']);
  expect(requests()[0].searchParams.get('date_from')).toBe('2026-03-01');
  expect(requests()[0].searchParams.has('page')).toBe(false);
  expect(requests()[0].searchParams.has('order')).toBe(false);
  await user.click(screen.getByRole('tab', { name: 'Documentos' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  expect(requests()).toHaveLength(1);
});

it('retries a failed temporal request without presenting failure as an empty series', async () => {
  let calls = 0;
  api(() => (++calls === 1 ? json({}, 503) : json(series())));
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await card().findByRole('alert');
  expect(card().queryByText(/Nenhum dado temporal/)).toBeNull();
  await user.click(card().getByRole('button', { name: 'Tentar novamente o gráfico temporal' }));
  await card().findByRole('table');
  expect(calls).toBe(2);
});

it('shows an empty state for a successful series without decisions', async () => {
  api(() => json({ total: 0, granularity: 'month', periods: [] }));
  const user = userEvent.setup();
  renderApp();
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await card().findByText(/Nenhum dado temporal encontrado/);
  expect(card().queryByRole('alert')).toBeNull();
});

it('does not replace the new cut with a late answer from the previous search', async () => {
  let resolve!: (r: Response) => void;
  const pending = new Promise<Response>((done) => {
    resolve = done;
  });
  const requests = api((url) =>
    url.searchParams.get('q') === 'primeiro tema' ? pending : json(series(99)),
  );
  const user = userEvent.setup();
  renderApp();
  const box = screen.getByRole('searchbox', { name: 'Pesquisar decisões' });
  await user.clear(box);
  await user.type(box, 'primeiro tema');
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await user.click(screen.getByRole('tab', { name: 'Panorama' }));
  await waitFor(() => expect(requests()).toHaveLength(1));
  expect(card().getByRole('status')).toHaveTextContent('Carregando');
  await user.clear(box);
  await user.type(box, 'segundo tema');
  await user.click(screen.getByRole('button', { name: 'Pesquisar' }));
  await card().findByText('99');
  await act(async () => resolve(json(series(12))));
  expect(card().getByText('99')).toBeInTheDocument();
});
