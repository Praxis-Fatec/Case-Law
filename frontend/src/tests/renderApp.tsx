import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import App from '../App';
import AddressProbe from './AddressProbe';

// The screen with its real routes, at any address — as when a link is opened
// directly or the page is reloaded there. `before` are entries already in the
// history behind it, for a test to tell where Back leads.
export function renderApp(path = '/', before: string[] = [], prefillSearch = true) {
  const view = render(
    <MemoryRouter initialEntries={[...before, path]} initialIndex={before.length}>
      <App />
      <AddressProbe />
    </MemoryRouter>,
  );
  // Existing search-flow tests start with a prepared expression. The real
  // landing page starts empty; its own test opts out of this fixture.
  const input = screen.queryByRole('searchbox', { name: 'Pesquisar decisões' });
  if (prefillSearch && input && !(input as HTMLInputElement).value) {
    fireEvent.change(input, { target: { value: 'prescrição intercorrente em execução fiscal' } });
  }
  return view;
}

export const currentAddress = () => screen.getByTestId('address').textContent;
