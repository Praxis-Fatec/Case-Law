import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import App from '../App';
import AddressProbe from './AddressProbe';

// The screen with its real routes, at any address — as when a link is opened
// directly or the page is reloaded there. `before` are entries already in the
// history behind it, for a test to tell where Back leads.
export function renderApp(path = '/', before: string[] = []) {
  return render(
    <MemoryRouter initialEntries={[...before, path]} initialIndex={before.length}>
      <App />
      <AddressProbe />
    </MemoryRouter>,
  );
}

export const currentAddress = () => screen.getByTestId('address').textContent;
