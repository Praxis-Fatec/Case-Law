import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import AppHeader from './components/AppHeader';
import CoveragePage, { COVERAGE_PATH } from './pages/CoveragePage';
import HomePage from './pages/HomePage';
import { HeaderSearchSlot } from './search/headerSearchSlot';
import SearchSessionProvider from './search/SearchSessionProvider';

function App() {
  // The place in the bar where the search screen puts its search.
  const [searchSlot, setSearchSlot] = useState<HTMLElement | null>(null);

  return (
    // The window's height and no more: each screen scrolls inside itself.
    <div className="app-shell">
      <AppHeader searchSlotRef={setSearchSlot} />
      {/* Above the routes, so the search outlives whichever screen shows it. */}
      <HeaderSearchSlot.Provider value={searchSlot}>
        <SearchSessionProvider>
          <Routes>
            {/* A decision's address is a child of the search, not a page of its
                own: the search stays mounted while the address changes, so its
                results, filters and order are still there when it changes back. */}
            <Route path="/" element={<HomePage />}>
              <Route path="decisoes/:source/:identifier" element={null} />
            </Route>
            {/* Its own page: the coverage describes the whole base, so nothing of
                the search is passed to it. */}
            <Route path={COVERAGE_PATH} element={<CoveragePage />} />
          </Routes>
        </SearchSessionProvider>
      </HeaderSearchSlot.Provider>
    </div>
  );
}

export default App;
