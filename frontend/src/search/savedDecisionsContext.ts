import { createContext, useContext } from 'react';
import type { DecisionKey, SavedDecision } from '../api/savedDecisions';

export type Bookmarks = {
  items: SavedDecision[];
  status: 'loading' | 'loaded' | 'failed';
  error: string;
  pending: Set<string>;
  retry: () => void;
  toggle: (key: DecisionKey) => Promise<void>;
};
export const SavedDecisionsContext = createContext<Bookmarks | null>(null);
export const useSavedDecisions = () => useContext(SavedDecisionsContext);
