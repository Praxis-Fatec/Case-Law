import { useEffect, useState } from 'react';
import { listCourts, type Court } from '../api/courts';

export type CourtsState =
  { status: 'loading' } | { status: 'loaded'; courts: Court[] } | { status: 'failed' };

export type CourtsList = { state: CourtsState; retry: () => void };

// Held by the screen, not by the filter panel: the panel is rendered into the
// top bar through a portal, so it is mounted a second time as the bar appears
// and would ask for the list again.
export function useCourts(): CourtsList {
  const [state, setState] = useState<CourtsState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;

    listCourts().then(
      (courts) => {
        if (active) {
          setState({ status: 'loaded', courts });
        }
      },
      () => {
        if (active) {
          setState({ status: 'failed' });
        }
      },
    );

    return () => {
      active = false;
    };
  }, [attempt]);

  return {
    state,
    retry: () => {
      setState({ status: 'loading' });
      setAttempt((current) => current + 1);
    },
  };
}
