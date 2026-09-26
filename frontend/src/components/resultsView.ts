// Which view of the applied search is up, and the ids that tie each tab to its
// panel.
export type ResultsView = 'documents' | 'panorama';

export const tabId = (view: ResultsView) => `results-tab-${view}`;
export const panelId = (view: ResultsView) => `results-panel-${view}`;
