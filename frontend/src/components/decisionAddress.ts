// The address of a decision: the same two identifiers the detail endpoint
// takes, so a copied link reopens exactly this decision.
//
// Here rather than in the screen that owns the route, because the decision
// detail now links to other decisions: two spellings of this path would drift
// apart without anything failing until a link led nowhere.
export const DETAIL_ROUTE = '/decisoes/:source/:identifier';

export const detailPath = (decision: { source: string; identifier: string }) =>
  `/decisoes/${encodeURIComponent(decision.source)}/${encodeURIComponent(decision.identifier)}`;
