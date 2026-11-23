import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';
import { readDetail, type SearchParams } from './search';

export type SavedSearch = {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  created_at: string;
};
export type SavedSearchParams = Omit<SearchParams, 'page' | 'page_size' | 'highlight'>;

export class SavedSearchError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'SavedSearchError';
  }
}

export function savedSearchParams(params: SearchParams): SavedSearchParams {
  // `mode` fica de fora junto com a página: uma busca salva guarda o recorte,
  // e como pesquisá-lo é escolha de quem a retoma.
  const { page: _page, page_size: _size, highlight: _highlight, mode: _mode, ...cut } = params;
  return cut;
}

function readSaved(value: unknown): SavedSearch {
  const row = value as Partial<SavedSearch> | null;
  if (
    !row ||
    typeof row.id !== 'string' ||
    !row.id ||
    typeof row.name !== 'string' ||
    !row.name.trim() ||
    !row.filters ||
    typeof row.filters !== 'object' ||
    Array.isArray(row.filters) ||
    typeof row.filters.q !== 'string' ||
    row.filters.q.trim().length < 2 ||
    typeof row.created_at !== 'string' ||
    !Number.isFinite(Date.parse(row.created_at))
  ) {
    throw new SavedSearchError(
      502,
      'O servidor retornou uma pesquisa salva em formato inválido. Tente novamente.',
    );
  }
  return row as SavedSearch;
}

async function call(path: string, options: RequestInit = {}): Promise<Response> {
  assertApiConfiguration();
  const response = await fetch(new URL(`${apiBaseUrl}/searches${path}`, window.location.origin), {
    ...options,
    headers: apiHeaders(options.body ? { 'Content-Type': 'application/json' } : {}),
  });
  if (!response.ok) {
    const detail = await readDetail(response);
    throw new SavedSearchError(
      response.status,
      response.status === 401
        ? 'Sua sessão expirou. Entre novamente.'
        : response.status === 404
          ? 'Esta pesquisa não está mais disponível.'
          : response.status === 422
            ? 'Revise o nome e os filtros da pesquisa e tente novamente.'
            : detail && response.status === 400
              ? detail
              : 'Não foi possível acessar as pesquisas salvas. Tente novamente.',
    );
  }
  return response;
}

export async function listSavedSearches(signal?: AbortSignal): Promise<SavedSearch[]> {
  const response = await call('', { signal });
  const body = (await response.json()) as { searches?: unknown };
  if (!Array.isArray(body.searches))
    throw new SavedSearchError(
      502,
      'Não foi possível ler a lista de pesquisas salvas. Tente novamente.',
    );
  return body.searches.map(readSaved);
}
export async function createSavedSearch(
  name: string,
  filters: SavedSearchParams,
  signal?: AbortSignal,
): Promise<SavedSearch> {
  return readSaved(
    await (
      await call('', { method: 'POST', body: JSON.stringify({ name, filters }), signal })
    ).json(),
  );
}
export async function getSavedSearch(id: string, signal?: AbortSignal): Promise<SavedSearch> {
  return readSaved(await (await call(`/${encodeURIComponent(id)}`, { signal })).json());
}
export async function deleteSavedSearch(id: string, signal?: AbortSignal): Promise<void> {
  await call(`/${encodeURIComponent(id)}`, { method: 'DELETE', signal });
}

export const savedSearchFailure = (error: unknown) =>
  error instanceof SavedSearchError
    ? error.message
    : 'Não foi possível acessar as pesquisas salvas. Verifique a conexão e tente novamente.';
