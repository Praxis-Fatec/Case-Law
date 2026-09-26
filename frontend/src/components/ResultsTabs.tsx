import { useRef, type KeyboardEvent } from 'react';
import { ChartBar, FileText, type Icon } from '@phosphor-icons/react';

import { panelId, tabId, type ResultsView } from './resultsView';

const TABS: { view: ResultsView; label: string; icon: Icon }[] = [
  { view: 'documents', label: 'Documentos', icon: FileText },
  { view: 'panorama', label: 'Panorama', icon: ChartBar },
];

type ResultsTabsProps = {
  value: ResultsView;
  onChange: (view: ResultsView) => void;
};

// Two views of the same applied search. Only the selected tab is in the Tab
// order; the arrows, Home and End move between them and select as they go,
// as a tab list is expected to behave.
function ResultsTabs({ value, onChange }: ResultsTabsProps) {
  const buttons = useRef<Record<ResultsView, HTMLButtonElement | null>>({
    documents: null,
    panorama: null,
  });

  const move = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((tab) => tab.view === value);
    const target = {
      ArrowRight: (index + 1) % TABS.length,
      ArrowLeft: (index - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }[event.key];

    if (target === undefined) {
      return;
    }

    event.preventDefault();
    const next = TABS[target].view;
    onChange(next);
    buttons.current[next]?.focus();
  };

  return (
    <div
      className="results-tabs"
      role="tablist"
      aria-label="Visualização dos resultados"
      onKeyDown={move}
    >
      {TABS.map(({ view, label, icon: TabIcon }) => {
        const selected = view === value;
        return (
          <button
            key={view}
            ref={(element) => {
              buttons.current[view] = element;
            }}
            type="button"
            role="tab"
            id={tabId(view)}
            aria-selected={selected}
            aria-controls={panelId(view)}
            tabIndex={selected ? 0 : -1}
            className={`results-tabs__tab${selected ? ' is-active' : ''}`}
            onClick={() => onChange(view)}
          >
            <TabIcon size={14} aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default ResultsTabs;
