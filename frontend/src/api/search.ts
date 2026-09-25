import { apiBaseUrl, assertApiConfiguration } from './client';

export type SearchDecisionMatch = {
  source: string;
  identifier: string;
  court: string;
  // The API declares these three nullable and means it: a third of the
  // collection has no class name, and the reporter is missing on part of it.
  case_number: string | null;
  judging_body: string | null;
  reporting_judge: string | null;
  decided_on: string;
  small_claims: string | null;
  source_url: string;
  source_url_reachable: boolean | null;
  snippet: string;
};

export type SearchDecisionResponse = {
  total: number;
  page: number;
  page_size: number;
  results: SearchDecisionMatch[];
};

// The two orders the API accepts. `relevance` is its default, so it is left
// out of the request: the default search stays the same request it always was.
export type SearchOrder = 'relevance' | 'date';

export const DEFAULT_ORDER: SearchOrder = 'relevance';

export async function searchDecisions(params: {
  q: string;
  page?: number;
  page_size?: number;
  // Applied by the API over every match, before paging — never on the page.
  order?: SearchOrder;
}): Promise<SearchDecisionResponse> {
  assertApiConfiguration();

  const url = new URL(`${apiBaseUrl}/decisions`, window.location.origin);
  url.searchParams.set('q', params.q);

  if (params.page) {
    url.searchParams.set('page', String(params.page));
  }

  if (params.page_size) {
    url.searchParams.set('page_size', String(params.page_size));
  }

  if (params.order && params.order !== DEFAULT_ORDER) {
    url.searchParams.set('order', params.order);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Search request failed with status ${response.status}`);
  }

  return (await response.json()) as SearchDecisionResponse;
}
