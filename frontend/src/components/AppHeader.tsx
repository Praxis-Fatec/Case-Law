import { NavLink, useLocation, useMatch } from 'react-router-dom';
import { Database } from '@phosphor-icons/react';

import { COVERAGE_PATH, type CoverageEntry } from '../pages/CoveragePage';

function AppHeader() {
  const location = useLocation();
  const onCoverage = useMatch(COVERAGE_PATH) !== null;

  // Opened from inside the app, the entry behind the page is where the reader
  // was — the search, or a decision in it — so the way back is Back. Clicked
  // again on the page itself, it replaces the entry and keeps that knowledge,
  // so Back never lands on a second copy of the same page.
  const state: CoverageEntry = onCoverage
    ? (location.state as CoverageEntry | null)
    : { fromApp: true };

  return (
    <header className="app-header">
      <nav className="app-header__nav" aria-label="Informações do sistema">
        <NavLink to={COVERAGE_PATH} state={state} replace={onCoverage} className="app-header__link">
          <Database size={17} aria-hidden="true" className="app-header__icon" />
          <span className="app-header__text">
            <span className="app-header__title">Cobertura da base</span>
            <span className="app-header__subtitle">Informações do sistema</span>
          </span>
        </NavLink>
      </nav>
    </header>
  );
}

export default AppHeader;
