import { createContext } from 'react';

// The place in the top bar where the search screen puts its search. The bar
// is above the routes and the search's state belongs to its screen, so the
// screen renders the search into this place rather than the bar owning it.
// Null until the bar is on screen, and on every screen without a search.
export const HeaderSearchSlot = createContext<HTMLElement | null>(null);
