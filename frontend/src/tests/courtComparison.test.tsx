import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CourtComparisonPanel from '../components/CourtComparisonPanel';
import { readComparison, type VolumeParams } from '../api/indicators';
import { renderApp } from './renderApp';

vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const courts = ['STJ', 'TJDFT', 'TRF1'].map((abbreviation) => ({
  abbreviation,
  name: abbreviation,
}));
const count = (value: string | null, decisions: number, total: number) => ({
  value,
  decisions,
  share: total ? (decisions / total) * 100 : 0,
});
const court = (abbreviation: string, total: number, denied: number) => ({
  abbreviation,
  name: abbreviation,
  total,
  outcomes: [
    count('negado', denied, total),
    count('provido', total - denied, total),
    count('parcialmente_provido', 0, total),
    count(null, 0, total),
  ],
  deliberations: [
    count('unanime', total, total),
    count('maioria', 0, total),
    count(null, 0, total),
  ],
  adherences: [count('seguiu', total, total), count('afastou', 0, total), count(null, 0, total)],
});
const data = { total: 10, courts: [court('STJ', 2, 1), court('TJDFT', 8, 4)] };
const params: VolumeParams = {
  q: 'dano moral',
  tribunal: ['STJ', 'TJDFT'],
  date_from: '2022-01-01',
  date_to: '2026-09-05',
  orgao_julgador: ['TURMA A'],
  relator: ['ANA'],
  classe_cnj: [198],
  published_from: '2023-01-01',
  published_to: '2026-10-01',
  resultado: ['negado'],
  orgao_julgador_excluido: ['TURMA B'],
  relator_excluido: ['BRUNO'],
};

function api(answer?: (url: URL) => Response | Promise<Response> | undefined) {
  const requests: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      requests.push(url);
      const custom = answer?.(url);
      if (custom) return custom;
      if (url.pathname === '/courts') return json({ courts });
      if (url.pathname === '/filters')
        return json({ judging_bodies: [], reporting_judges: [], procedural_classes: [] });
      if (url.pathname === '/indicators/comparison') return json(data);
      if (url.pathname === '/indicators/coverage')
        return json({
          documents: 20,
          state: 'loaded',
          updated_at: '2026-11-14T09:10:00Z',
          courts: [
            {
              abbreviation: 'STJ',
              name: 'STJ',
              documents: 10,
              first: '1998-01-01',
              last: '2026-11-14',
            },
            {
              abbreviation: 'TJDFT',
              name: 'TJDFT',
              documents: 10,
              first: '2026-01-01',
              last: '2026-11-14',
            },
          ],
        });
      if (url.pathname === '/indicators/concentration')
        return json({
          total: 2,
          limit: 1,
          judging_bodies: {
            groups: [{ name: 'TURMA A', decisions: 1, share: 50 }],
            other: { groups: 2, decisions: 1, share: 50 },
            missing: 0,
          },
          reporting_judges: {
            groups: [],
            other: { groups: 0, decisions: 0, share: 0 },
            missing: 0,
          },
        });
      if (url.pathname === '/decisions')
        return json({ total: 10, page: 1, page_size: 6, results: [] });
      return json({});
    }),
  );
  return requests;
}

function panel(overrides: Partial<Parameters<typeof CourtComparisonPanel>[0]> = {}) {
  const onClose = vi.fn();
  const onDocuments = vi.fn();
  return {
    ...render(
      <CourtComparisonPanel
        params={params}
        courts={courts}
        onClose={onClose}
        onDocuments={onDocuments}
        returnFocus={null}
        {...overrides}
      />,
    ),
    onClose,
    onDocuments,
  };
}

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});
afterEach(() => vi.unstubAllGlobals());

describe('court comparison', () => {
  it('explains why different instances cannot be ranked by appeal outcome rates', async () => {
    api();
    panel();
    await screen.findByRole('table');
    const warning = screen.getByRole('note');
    expect(warning).toBeVisible();
    expect(warning).toHaveTextContent('Instâncias diferentes');
    expect(warning).toHaveTextContent(/julgam recursos distintos/);
    expect(warning).toHaveTextContent(/por isso taxas de provimento não medem rigor/);
    expect(warning).toHaveAttribute('aria-live', 'polite');
  });

  it('omits the warning for courts at the same level, even across jurisdictions', async () => {
    api();
    panel({ params: { q: 'dano moral', tribunal: ['TJDFT', 'TRF1'] } });
    await screen.findByRole('table');
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });

  it('updates the warning immediately when court selection changes', async () => {
    api();
    panel();
    await screen.findByRole('table');
    expect(screen.getByRole('note')).toBeVisible();
    fireEvent.change(screen.getByLabelText('Tribunal A'), { target: { value: 'TRF1' } });
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Tribunal A'), { target: { value: 'STJ' } });
    expect(screen.getByRole('note')).toHaveTextContent('Instâncias diferentes');
    await screen.findByRole('table');
  });

  it('keeps every applied filter in the comparison and each court concentration request', async () => {
    const requests = api();
    panel();
    await screen.findByRole('table', { name: 'Critérios por tribunal' });
    const compared = requests.find((url) => url.pathname === '/indicators/comparison')!;
    for (const [name, value] of Object.entries(params)) {
      expect(compared.searchParams.getAll(name)).toEqual(
        Array.isArray(value) ? value.map(String) : [value],
      );
    }
    const grouped = requests.filter((url) => url.pathname === '/indicators/concentration');
    expect(grouped.map((url) => url.searchParams.getAll('tribunal'))).toEqual([['STJ'], ['TJDFT']]);
    expect(
      grouped.every(
        (url) =>
          url.searchParams.get('orgao_julgador') === 'TURMA A' &&
          url.searchParams.get('resultado') === 'negado',
      ),
    ).toBe(true);
    expect(screen.getByText('Cobertura parcial')).toBeVisible();
    expect(screen.getAllByText(/Última coleta da base/)).toHaveLength(2);
    const groupRow = screen.getByRole('rowheader', { name: 'Órgãos julgadores' }).parentElement!;
    expect(
      within(groupRow)
        .getAllByRole('cell')
        .map((item) => item.textContent),
    ).toEqual(['STJ: 3', 'TJDFT: 3']);
  });

  it('reuses one count scale for both courts and all three distributions', async () => {
    api();
    panel();
    await screen.findByRole('table');
    fireEvent.click(screen.getByText('Mais critérios'));
    const axes = document.querySelectorAll('.court-comparison__chart .outcome-horizontal__axis');
    expect(axes).toHaveLength(6);
    expect(new Set([...axes].map((axis) => axis.textContent)).size).toBe(1);
    const left = screen
      .getByRole('region', { name: 'Resultado do STJ' })
      .querySelector<HTMLElement>('[data-outcome="negado"]')!;
    const right = screen
      .getByRole('region', { name: 'Resultado do TJDFT' })
      .querySelector<HTMLElement>('[data-outcome="negado"]')!;
    expect(parseFloat(right.style.width)).toBe(parseFloat(left.style.width) * 4);
    expect(screen.getByText('Base dos percentuais: 2 decisões deste tribunal.')).toBeVisible();
    expect(screen.getByText('Base dos percentuais: 8 decisões deste tribunal.')).toBeVisible();
  });

  it('keeps the empty court column with a reason and no documents action', async () => {
    api((url) =>
      url.pathname === '/indicators/comparison'
        ? json({ total: 2, courts: [court('STJ', 2, 1), court('TJDFT', 0, 0)] })
        : undefined,
    );
    panel();
    await screen.findByRole('table');
    expect(
      screen.getByText('Nenhuma decisão neste recorte. Revise a expressão ou os filtros.'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: /Ver documentos do TJDFT/ })).toBeDisabled();
    fireEvent.click(screen.getByText('Mais critérios'));
    expect(screen.getByText(/Nenhuma decisão corresponde à expressão/)).toBeVisible();
    expect(screen.getByRole('region', { name: 'Indicadores do TJDFT' })).toBeVisible();
  });

  it('distinguishes unavailable comparison data from zero and retries', async () => {
    let failed = true;
    api((url) => (url.pathname === '/indicators/comparison' && failed ? json({}, 503) : undefined));
    panel();
    expect(await screen.findByRole('alert')).toHaveTextContent(/indisponíveis/);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    failed = false;
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('table')).toBeVisible();
  });

  it('preserves available metrics when coverage or grouping is unavailable', async () => {
    api((url) =>
      ['/indicators/coverage', '/indicators/concentration'].includes(url.pathname)
        ? json({}, 503)
        : undefined,
    );
    panel();
    await screen.findByRole('table');
    expect(screen.getAllByText('Cobertura indisponível')).toHaveLength(2);
    expect(screen.getAllByText('Indisponível')).toHaveLength(2);
    expect(screen.getByRole('button', { name: /Ver documentos do STJ/ })).toBeEnabled();
  });

  it('replaces the chosen court without losing the other filters or showing stale counts', async () => {
    let complete: ((response: Response) => void) | undefined;
    const requests = api((url) =>
      url.pathname === '/indicators/comparison' &&
      url.searchParams.getAll('tribunal').includes('TRF1')
        ? new Promise<Response>((resolve) => {
            complete = resolve;
          })
        : undefined,
    );
    panel();
    await screen.findByRole('table');
    fireEvent.change(screen.getByLabelText('Tribunal B'), { target: { value: 'TRF1' } });
    expect(screen.getByText('Carregando comparação…')).toBeVisible();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    await waitFor(() => expect(complete).toBeDefined());
    await act(async () =>
      complete!(json({ total: 2, courts: [court('STJ', 2, 1), court('TRF1', 0, 0)] })),
    );
    expect(await screen.findByRole('columnheader', { name: 'TRF1' })).toBeVisible();
    const request = requests
      .filter((url) => url.pathname === '/indicators/comparison')
      .slice(-1)[0];
    expect(request.searchParams.getAll('tribunal')).toEqual(['STJ', 'TRF1']);
    expect(request.searchParams.get('date_from')).toBe(params.date_from);
    expect(
      within(screen.getByLabelText('Tribunal A')).getByRole('option', { name: 'TRF1' }),
    ).toBeDisabled();
  });

  it('opens the selected court documents with that court total', async () => {
    api();
    const { onDocuments } = panel();
    fireEvent.click(await screen.findByRole('button', { name: /Ver documentos do TJDFT/ }));
    expect(onDocuments).toHaveBeenCalledWith('TJDFT', 8);
  });

  it('closes on Escape and restores focus after unmount', () => {
    api();
    const trigger = document.createElement('button');
    document.body.append(trigger);
    trigger.focus();
    const { onClose, unmount } = panel({ returnFocus: trigger });
    expect(screen.getByRole('button', { name: 'Fechar comparação de tribunais' })).toHaveFocus();
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
    expect(onClose).toHaveBeenCalledOnce();
    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it('asks for a second court without issuing an unrestricted comparison', () => {
    const requests = api();
    panel({ params: { q: 'dano' }, courts: [] });
    expect(screen.getByRole('status')).toHaveTextContent(/Selecione dois tribunais diferentes/);
    expect(requests).toHaveLength(0);
  });

  it('keeps missing and malformed counts unknown instead of inventing zeros', () => {
    const parsed = readComparison({
      total: -1,
      courts: [
        {
          abbreviation: 'STJ',
          total: null,
          outcomes: [{ value: 'negado', decisions: '2', share: -1 }, { decisions: 1 }, null],
        },
      ],
    });
    expect(parsed.total).toBeNull();
    expect(parsed.courts[0].outcomes).toEqual([{ value: 'negado', decisions: null, share: null }]);
  });

  it('loads only after the results action opens the dialog', async () => {
    const requests = api();
    renderApp();
    fireEvent.click(screen.getByRole('button', { name: 'Pesquisar' }));
    const trigger = await screen.findByRole('button', { name: 'Comparar tribunais' });
    expect(requests.some((url) => url.pathname === '/indicators/comparison')).toBe(false);
    fireEvent.click(trigger);
    expect(await screen.findByRole('dialog', { name: 'Comparar tribunais' })).toBeVisible();
    await screen.findByRole('table');
    fireEvent.click(screen.getByRole('button', { name: /Ver documentos do TJDFT/ }));
    await waitFor(() =>
      expect(
        requests.some(
          (url) => url.pathname === '/decisions' && url.searchParams.get('tribunal') === 'TJDFT',
        ),
      ).toBe(true),
    );
  });
});
