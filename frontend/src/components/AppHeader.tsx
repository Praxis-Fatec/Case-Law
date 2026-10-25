import { NavLink, useLocation, useMatch } from 'react-router-dom';
import { Database, SignOut, UsersThree } from '@phosphor-icons/react';

import { COVERAGE_PATH, type CoverageEntry } from '../pages/CoveragePage';
import { TEAM_PATH } from '../pages/TeamPage';
import { useSession } from '../session/sessionContext';

type AppHeaderProps = {
  // Given the place where a screen may put its search, empty on the others.
  searchSlotRef?: (element: HTMLElement | null) => void;
};

function AppHeader({ searchSlotRef }: AppHeaderProps) {
  const location = useLocation();
  const onCoverage = useMatch(COVERAGE_PATH) !== null;
  const onTeam = useMatch(TEAM_PATH) !== null;
  const session = useSession();
  const person = session.status === 'signed in' ? session.person : null;

  // Opened from inside the app, the entry behind the page is where the reader
  // was — the search, or a decision in it — so the way back is Back. Clicked
  // again on the page itself, it replaces the entry and keeps that knowledge,
  // so Back never lands on a second copy of the same page.
  const state: CoverageEntry = onCoverage
    ? (location.state as CoverageEntry | null)
    : { fromApp: true };

  return (
    <header className="app-header">
      <div ref={searchSlotRef} className="app-header__search" />
      <nav className="app-header__nav" aria-label="Informações do sistema">
        <NavLink to={COVERAGE_PATH} state={state} replace={onCoverage} className="app-header__link">
          <Database size={14} aria-hidden="true" className="app-header__icon" />
          <span className="app-header__text">
            <span className="app-header__title">Cobertura da base</span>
            <span className="app-header__subtitle">Informações do sistema</span>
          </span>
        </NavLink>

        {/* Only a manager administers, so only a manager is offered the way
            there. The API refuses the rest regardless; this keeps the bar from
            showing a door that would close in their face. */}
        {person?.role === 'gerente' && (
          <NavLink to={TEAM_PATH} replace={onTeam} className="app-header__link">
            <UsersThree size={14} aria-hidden="true" className="app-header__icon" />
            <span className="app-header__text">
              <span className="app-header__title">Usuários</span>
              <span className="app-header__subtitle">Quem tem acesso</span>
            </span>
          </NavLink>
        )}

        {person && (
          <div className="app-header__account">
            <span className="app-header__who" title={person.email}>
              {person.name}
            </span>
            <button type="button" className="app-header__leave" onClick={session.signOut}>
              <SignOut size={14} aria-hidden="true" />
              Sair
            </button>
          </div>
        )}
      </nav>
    </header>
  );
}

export default AppHeader;
