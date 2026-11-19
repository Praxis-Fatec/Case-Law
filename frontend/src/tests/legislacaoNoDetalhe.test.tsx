import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CitedLegislation from '../components/CitedLegislation';

// O mesmo que `doutrinaNoDetalhe` faz, e pelo mesmo motivo: `VITE_API_URL` vem
// do `.env`, que não é versionado. Sem isto a suíte passa na máquina de quem
// tem o arquivo e quebra no CI, que não tem.
vi.mock('../api/client', () => ({
  apiBaseUrl: 'http://localhost:8000',
  assertApiConfiguration: () => undefined,
}));

/**
 * The legislation block, and the three answers it has to tell apart.
 *
 * A reference it could read, a reference it could not, and no reference at all.
 * The second is the one a careless block would drop, and dropping it shows a
 * decision applying less law than it did — with nothing on screen saying so.
 * The third is ordinary: the TJDFT collection catalogues none and a third of
 * the STJ's does not either, so it can never read as a broken screen.
 *
 * Nothing in this block links out. A link to the wrong statute is worse than a
 * citation the reader looks up, so the test asserts the absence.
 */

const DECRETO_LEI = {
  sphere: 'FED',
  act_type: 'DEL',
  number: 3365,
  year: 1941,
  article: '26',
  paragraphs: ['2'],
  items: [],
  letters: [],
  recognised: true,
  raw: 'LEG:FED DEL:003365 ANO:1941 ART:00026 PAR:00002',
};

const CONSTITUICAO = {
  sphere: 'FED',
  act_type: 'CFB',
  number: null,
  year: 1988,
  article: '105',
  paragraphs: [],
  items: ['3', '4'],
  letters: ['A', 'C'],
  recognised: true,
  raw: 'LEG:FED CFB:****** ANO:1988 ART:00105 INC:00003 INC:00004 LET:A LET:C',
};

const CRUA = {
  sphere: 'FED',
  act_type: null,
  number: null,
  year: null,
  article: null,
  paragraphs: [],
  items: [],
  letters: [],
  recognised: false,
  raw: 'LEG:FED ***** SUM(STF) SUMULA DO SUPREMO TRIBUNAL FEDERAL SUM:000282',
};

function answering(body: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  });
}

function block() {
  return render(
    <CitedLegislation source="stj-espelhos" identifier="000738063" headingId="legislacao" />,
  );
}

beforeEach(() => {
  vi.stubGlobal('fetch', answering({ results: [] }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('os três estados da história', () => {
  it('lista a legislação em forma legível', async () => {
    vi.stubGlobal('fetch', answering({ results: [DECRETO_LEI] }));
    block();

    expect(await screen.findByText('Decreto-Lei 3.365/1941, art. 26, §2º')).toBeInTheDocument();
  });

  it('o estado vazio diz que não há referência catalogada, e não é falha', async () => {
    block();

    const texto = await screen.findByText(/Nenhuma referência legislativa catalogada/);

    expect(texto).toBeInTheDocument();
    // Uma resposta não se anuncia como falha.
    expect(screen.queryByText(/Não foi possível consultar/)).not.toBeInTheDocument();
  });

  it('a referência não reconhecida aparece crua, e dito que é crua', async () => {
    vi.stubGlobal('fetch', answering({ results: [CRUA] }));
    block();

    expect(await screen.findByText(/não reconheceu/)).toBeInTheDocument();
    expect(screen.getByText(CRUA.raw)).toBeInTheDocument();
  });
});

describe('o que mais pode acontecer', () => {
  it('carregando diz que está procurando', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    block();

    expect(screen.getByRole('status')).toHaveTextContent(/Procurando a legislação/);
  });

  it('a falha é falha, não ausência de lei', async () => {
    vi.stubGlobal('fetch', answering({ detail: 'nope' }, false));
    block();

    expect(await screen.findByText(/Não foi possível consultar a legislação/)).toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma referência legislativa/)).not.toBeInTheDocument();
  });
});

describe('o que o bloco não faz', () => {
  it('não leva a portal nenhum de legislação', async () => {
    vi.stubGlobal('fetch', answering({ results: [DECRETO_LEI, CONSTITUICAO, CRUA] }));
    block();

    await screen.findByText('Decreto-Lei 3.365/1941, art. 26, §2º');
    const bloco = screen.getByRole('region', { name: /Legislação citada/ });

    expect(within(bloco).queryAllByRole('link')).toHaveLength(0);
    expect(within(bloco).getByText(/link para a lei errada é pior/)).toBeInTheDocument();
  });

  it('não mistura a referência crua com as lidas', async () => {
    vi.stubGlobal('fetch', answering({ results: [DECRETO_LEI, CRUA] }));
    block();

    const itens = within(await screen.findByRole('list')).getAllByRole('listitem');

    expect(itens).toHaveLength(2);
    expect(itens[0]).toHaveTextContent('Decreto-Lei 3.365/1941, art. 26, §2º');
    expect(itens[1]).toHaveTextContent(CRUA.raw);
  });
});

describe('a citação inteira, como uma petição a escreveria', () => {
  it('a Constituição vem pelo ano, com inciso em romano e alínea em minúscula', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONSTITUICAO] }));
    block();

    expect(
      await screen.findByText('Constituição Federal de 1988, art. 105, III e IV, a e c'),
    ).toBeInTheDocument();
  });

  it('mantém a ordem em que o tribunal listou', async () => {
    vi.stubGlobal('fetch', answering({ results: [CONSTITUICAO, DECRETO_LEI] }));
    block();

    const itens = within(await screen.findByRole('list')).getAllByRole('listitem');

    expect(itens[0]).toHaveTextContent(/Constituição Federal de 1988/);
    expect(itens[1]).toHaveTextContent(/Decreto-Lei 3\.365\/1941/);
  });
});
