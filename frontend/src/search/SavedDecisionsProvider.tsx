import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  bookmarkFailure,
  bookmarkKey,
  listSavedDecisions,
  removeDecision,
  saveDecision,
  type DecisionKey,
  type SavedDecision,
} from '../api/savedDecisions';
import { SavedDecisionsContext, type Bookmarks } from './savedDecisionsContext';

export default function SavedDecisionsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<SavedDecision[]>([]);
  const [status, setStatus] = useState<Bookmarks['status']>('loading');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const inFlight = useRef(new Set<string>());
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    listSavedDecisions(controller.signal).then(
      (rows) => {
        if (!controller.signal.aborted) {
          setItems(rows);
          setStatus('loaded');
          setError('');
        }
      },
      (failure) => {
        if (!controller.signal.aborted) {
          setStatus('failed');
          setError(bookmarkFailure(failure));
        }
      },
    );
    return () => controller.abort();
  }, [attempt]);
  const toggle = async (key: DecisionKey) => {
    const id = bookmarkKey(key);
    if (inFlight.current.has(id) || status !== 'loaded') return;
    inFlight.current.add(id);
    setPending(new Set(inFlight.current));
    try {
      const exists = items.some((item) => bookmarkKey(item) === id);
      if (exists) {
        await removeDecision(key);
        if (alive.current) setItems((rows) => rows.filter((item) => bookmarkKey(item) !== id));
      } else {
        const saved = await saveDecision(key);
        if (alive.current)
          setItems((rows) => [saved, ...rows.filter((item) => bookmarkKey(item) !== id)]);
      }
    } finally {
      inFlight.current.delete(id);
      if (alive.current) setPending(new Set(inFlight.current));
    }
  };
  return (
    <SavedDecisionsContext.Provider
      value={{
        items,
        status,
        error,
        pending,
        toggle,
        retry: () => {
          setStatus('loading');
          setAttempt((value) => value + 1);
        },
      }}
    >
      {children}
    </SavedDecisionsContext.Provider>
  );
}
