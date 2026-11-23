import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderApp } from './renderApp';

// Only the address of the API is replaced: the request code under test is the
// real one, so what is asked of the endpoint is what the app sends.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://api.test',
  assertApiConfiguration: () => undefined,
}));

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const COVERAGE = {
  documents: 991163,
  first: '1989-02-19',
  last: '2026-09-17',
  courts: [
    {
      abbreviation: 'STJ',
      name: 'Superior Tribunal de Justiça',
      documents: 876996,
      first: '1989-02-19',
      last: '2026-08-26',
    },
  ],
  state: 'loaded',
  updated_at: '2026-10-25T03:30:55Z',
  vocabulary_updated_at: '2026-09-01T03:14:09Z',
};

// The four shapes RF16 has to tell apart, in the order the API sends them.
const SOURCES = [
  {
    code: 'tjdft-jurisdf',
    name: 'TJDFT JurisDF',
    content: 'decisao',
    availability: 'ativa',
    state: 'loaded',
    last_collection: '2026-10-10T15:24:11Z',
    last_attempt: '2026-10-10T15:24:11Z',
    last_attempt_failed: false,
    items: 114167,
    undated_items: 0,
    first: '2025-09-17',
    last: '2026-09-17',
    precision: 'dia',
  },
  {
    code: 'stj-espelhos',
    name: 'STJ Espelhos de Acórdãos',
    content: 'decisao',
    availability: 'ativa',
    state: 'loaded',
    last_collection: '2026-10-10T16:07:38Z',
    last_attempt: '2026-10-25T03:21:56Z',
    last_attempt_failed: true,
    items: 876996,
    undated_items: 14,
    first: '1989-02-19',
    last: '2026-08-26',
    precision: 'dia',
  },
  {
    code: 'stj-bdjur',
    name: 'BDJur Biblioteca Digital do STJ',
    content: 'doutrina',
    availability: 'bloqueada',
    state: 'loaded',
    last_collection: '2026-10-25T03:30:55Z',
    last_attempt: '2026-10-25T03:30:55Z',
    last_attempt_failed: false,
    items: 797,
    undated_items: 0,
    first: '1953-01-01',
    last: '2026-01-01',
    precision: 'ano',
  },
  {
    code: 'stj-precedentes',
    name: 'STJ Precedentes Qualificados',
    content: 'precedente',
    availability: 'ativa',
    state: 'never_loaded',
    last_collection: null,
    last_attempt: null,
    last_attempt_failed: false,
    items: 0,
    undated_items: 0,
    first: null,
    last: null,
    precision: 'nenhuma',
  },
];

type Answer = () => Response | Promise<Response>;

function installApi({
  coverage = () => json(COVERAGE),
  sources = () => json(SOURCES),
}: { coverage?: Answer; sources?: Answer } = {}) {
  const sourceRequests: URL[] = [];

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));

      if (url.pathname === '/indicators/coverage') {
        return coverage();
      }

      if (url.pathname === '/indicators/sources') {
        sourceRequests.push(url);
        return sources();
      }

      return json({ courts: [] });
    }),
  );

  return { sourceRequests };
}

const section = () => within(screen.getByRole('region', { name: 'Estado de cada fonte' }));

const rowFor = async (name: string) =>
  (await section().findByRole('rowheader', { name: new RegExp(name) })).closest('tr')!;

async function openCoverage() {
  renderApp('/cobertura');
  return userEvent.setup();
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the source list', () => {
  it('asks the endpoint with nothing attached, as the coverage does', async () => {
    const { sourceRequests } = installApi();
    await openCoverage();

    await waitFor(() => expect(sourceRequests).toHaveLength(1));
    expect(sourceRequests[0].search).toBe('');
  });

  it('shows every source the answer carries, including one that delivered nothing', async () => {
    installApi();
    await openCoverage();

    for (const name of ['TJDFT JurisDF', 'STJ Espelhos', 'BDJur', 'STJ Precedentes Qualificados']) {
      expect(await rowFor(name)).toBeTruthy();
    }
  });

  it('never leaves a value looking unformatted', async () => {
    installApi();
    await openCoverage();
    await rowFor('TJDFT JurisDF');

    expect(screen.getByRole('main')).not.toHaveTextContent(/null|undefined|NaN|Invalid Date/);
  });
});

describe('a source being collected', () => {
  it('says so, with the date of the collection and the period it covers', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('TJDFT JurisDF');

    expect(within(row).getByText('Coletando')).toBeInTheDocument();
    // 15:24 UTC is 12:24 in Brasília, which is the reader's clock.
    expect(within(row).getByText('10/10/2026, 12:24')).toBeInTheDocument();
    expect(within(row).getByText('17/09/2025 – 17/09/2026')).toBeInTheDocument();
  });
});

describe('a source whose last attempt failed', () => {
  it('keeps the date of the collection that worked and names the failure beside it', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('STJ Espelhos');

    expect(within(row).getByText('Última tentativa falhou')).toBeInTheDocument();
    expect(within(row).getByText('10/10/2026, 13:07')).toBeInTheDocument();
    expect(within(row).getByText(/Tentativa em 25\/10\/2026, 00:21 falhou/)).toBeInTheDocument();
  });

  it('counts the undated items rather than letting the period look complete', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('STJ Espelhos');

    expect(within(row).getByText('14 sem data')).toBeInTheDocument();
  });
});

describe('a source that was never collected', () => {
  it('says that, instead of showing an empty row', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('STJ Precedentes Qualificados');

    expect(within(row).getByText('Nunca coletada')).toBeInTheDocument();
    expect(within(row).getByText('Nenhuma coleta registrada')).toBeInTheDocument();
    expect(within(row).getByText('Sem período')).toBeInTheDocument();
  });

  it('is not confused with one whose every attempt failed', async () => {
    installApi({
      sources: () =>
        json([
          {
            ...SOURCES[3],
            state: 'all_loads_failed',
            last_attempt: '2026-10-23T01:06:53Z',
            last_attempt_failed: true,
          },
        ]),
    });
    await openCoverage();
    const row = await rowFor('STJ Precedentes Qualificados');

    expect(within(row).getByText('Última tentativa falhou')).toBeInTheDocument();
    expect(within(row).getByText(/Nenhuma concluída/)).toBeInTheDocument();
    expect(within(row).queryByText('Nunca coletada')).not.toBeInTheDocument();
  });
});

describe('a source the court has blocked', () => {
  it('says the block, and keeps what the source had already delivered', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('BDJur');

    expect(within(row).getByText('Acervo fechado')).toBeInTheDocument();
    expect(within(row).getByText('797')).toBeInTheDocument();
  });

  it('writes a year-only period as the year, never as a first of January', async () => {
    installApi();
    await openCoverage();
    const row = await rowFor('BDJur');

    expect(within(row).getByText('1953 – 2026')).toBeInTheDocument();
    expect(within(row).queryByText(/01\/01\/1953/)).not.toBeInTheDocument();
  });
});

describe('when the source list cannot be read', () => {
  it('says so there, and leaves the rest of the coverage standing', async () => {
    installApi({ sources: () => json({ detail: 'not published' }, 503) });
    await openCoverage();

    expect(
      await section().findByText('O estado das fontes está indisponível no momento.'),
    ).toBeInTheDocument();
    // The scope is still an answer, and the reason the two are asked apart.
    expect(await screen.findAllByText(/991\.163/)).not.toHaveLength(0);
  });

  it('never shows an empty catalogue as if there were no sources', async () => {
    installApi({ sources: () => json([]) });
    await openCoverage();

    expect(
      await section().findByText('O estado das fontes não foi informado.'),
    ).toBeInTheDocument();
  });
});
