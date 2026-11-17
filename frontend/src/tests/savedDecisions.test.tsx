import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import {
  listSavedDecisions,
  removeDecision,
  saveDecision,
  type SavedDecision,
} from '../api/savedDecisions';
import SavedDecisionsProvider from '../search/SavedDecisionsProvider';
import SaveDecisionButton from '../components/SaveDecisionButton';
import SavedSearchesDrawer from '../components/SavedSearchesDrawer';
import AddressProbe from './AddressProbe';

vi.mock('../api/savedDecisions', async (original) => ({
  ...(await original<typeof import('../api/savedDecisions')>()),
  listSavedDecisions: vi.fn(),
  saveDecision: vi.fn(),
  removeDecision: vi.fn(),
}));
vi.mock('../api/savedSearches', async (original) => ({
  ...(await original<typeof import('../api/savedSearches')>()),
  listSavedSearches: vi.fn(async () => []),
}));
const saved: SavedDecision = {
  source: 'tjdft-jurisdf',
  identifier: '1000001',
  court: 'TJDFT',
  case_number: '0700001',
  summary: 'Dano moral. Recurso negado.',
  decided_on: '2026-03-10',
  created_at: '2026-11-17T12:00:00Z',
  available: true,
};
const key = { source: saved.source, identifier: saved.identifier };
const noop = () => undefined;
function mount(drawer = false) {
  return render(
    <MemoryRouter>
      <SavedDecisionsProvider>
        <div aria-label="Resultado">
          <SaveDecisionButton {...key} />
        </div>
        <div aria-label="Detalhe">
          <SaveDecisionButton {...key} />
        </div>
        {drawer && (
          <SavedSearchesDrawer onClose={noop} onCount={noop} onResume={noop} onRemoved={noop} />
        )}
        <AddressProbe />
      </SavedDecisionsProvider>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listSavedDecisions).mockResolvedValue([]);
  vi.mocked(saveDecision).mockResolvedValue(saved);
  vi.mocked(removeDecision).mockResolvedValue(undefined);
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});

it('saves once, synchronizes result and detail, removes and restores persisted state on remount', async () => {
  let finish!: (value: SavedDecision) => void;
  vi.mocked(saveDecision).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const view = mount();
  const result = within(screen.getByLabelText('Resultado'));
  await waitFor(() => expect(result.getByRole('button')).toBeEnabled());
  fireEvent.click(result.getByRole('button'));
  fireEvent.click(result.getByRole('button'));
  expect(saveDecision).toHaveBeenCalledTimes(1);
  expect(saveDecision).toHaveBeenCalledWith(key);
  finish(saved);
  await waitFor(() =>
    expect(
      screen.getAllByRole('button', { name: 'Remover decisão dos itens salvos' }),
    ).toHaveLength(2),
  );
  view.unmount();
  vi.mocked(listSavedDecisions).mockResolvedValue([saved]);
  mount();
  await waitFor(() =>
    expect(
      screen.getAllByRole('button', { name: 'Remover decisão dos itens salvos' }),
    ).toHaveLength(2),
  );
  fireEvent.click(screen.getAllByRole('button', { name: 'Remover decisão dos itens salvos' })[0]);
  await waitFor(() =>
    expect(screen.getAllByRole('button', { name: 'Salvar decisão' })).toHaveLength(2),
  );
  expect(removeDecision).toHaveBeenCalledWith(key);
});

it('does not falsely mark a failed save and lets the person retry', async () => {
  vi.mocked(saveDecision).mockRejectedValueOnce(new Error('Falha ao salvar. Tente novamente.'));
  mount();
  const result = within(screen.getByLabelText('Resultado'));
  await waitFor(() => expect(result.getByRole('button')).toBeEnabled());
  fireEvent.click(result.getByRole('button'));
  expect(await result.findByRole('alert')).toHaveTextContent('Falha ao salvar');
  expect(result.getByRole('button')).toHaveAttribute('aria-pressed', 'false');
  fireEvent.click(result.getByRole('button'));
  await waitFor(() => expect(result.getByRole('button')).toHaveAttribute('aria-pressed', 'true'));
});

it('offers the two categories, opens the saved decision address and removes only after success', async () => {
  vi.mocked(listSavedDecisions).mockResolvedValue([saved]);
  vi.mocked(removeDecision).mockRejectedValueOnce(new Error('Falha ao remover.'));
  mount(true);
  const drawer = within(screen.getByRole('dialog', { name: 'Itens salvos' }));
  fireEvent.click(drawer.getByRole('button', { name: /Decisões/ }));
  const card = await drawer.findByRole('article', { name: 'Decisão 0700001' });
  expect(drawer.getByRole('button', { name: /Pesquisas/ })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  expect(within(card).getByRole('link', { name: 'Abrir decisão' })).toHaveAttribute(
    'href',
    '/decisoes/tjdft-jurisdf/1000001',
  );
  fireEvent.click(within(card).getByRole('button', { name: 'Remover decisão 0700001' }));
  expect(await within(card).findByRole('alert')).toHaveTextContent('Falha ao remover');
  expect(card).toBeInTheDocument();
  fireEvent.click(within(card).getByRole('button', { name: 'Remover decisão 0700001' }));
  expect(await drawer.findByText('Guarde sua primeira decisão')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Salvar decisão', hidden: true })).toHaveLength(2);
});

it('preserves unavailable bookmarks with an explanation and no broken open link', async () => {
  vi.mocked(listSavedDecisions).mockResolvedValue([{ ...saved, available: false }]);
  mount(true);
  fireEvent.click(screen.getByRole('button', { name: /Decisões/ }));
  expect(
    await screen.findByText(/Esta decisão não está mais disponível no acervo/),
  ).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Abrir decisão' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Remover decisão 0700001' })).toBeEnabled();
});

it('does not show an empty collection when loading fails and retries explicitly', async () => {
  vi.mocked(listSavedDecisions).mockRejectedValueOnce(new Error('Banco indisponível.'));
  mount(true);
  fireEvent.click(screen.getByRole('button', { name: /Decisões/ }));
  const drawer = within(screen.getByRole('dialog', { name: 'Itens salvos' }));
  expect(await drawer.findByRole('alert')).toHaveTextContent('Banco indisponível');
  expect(drawer.queryByText('Guarde sua primeira decisão')).not.toBeInTheDocument();
  fireEvent.click(drawer.getByRole('button', { name: 'Tentar novamente' }));
  expect(await drawer.findByText('Guarde sua primeira decisão')).toBeInTheDocument();
});
