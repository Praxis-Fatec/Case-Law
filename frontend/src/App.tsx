import { Routes, Route } from 'react-router-dom';
import AppHeader from './components/AppHeader';
import CoveragePage, { COVERAGE_PATH } from './pages/CoveragePage';
import HomePage from './pages/HomePage';
import SearchSessionProvider from './search/SearchSessionProvider';

function App() {
  return (
    <div>
      <AppHeader />
      {/* Above the routes, so the search outlives whichever screen shows it. */}
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
    </div>
  );
}

export default App;
