import { apiBaseUrl, assertApiConfiguration } from './client';
import { apiHeaders } from './token';

export type SavedDecision = {
  source: string;
  identifier: string;
  court: string;
  case_number: string | null;
  summary: string;
  decided_on: string | null;
  created_at: string;
  available: boolean;
};
export type DecisionKey = Pick<SavedDecision, 'source' | 'identifier'>;
export const bookmarkKey = (item: DecisionKey) => JSON.stringify([item.source, item.identifier]);

async function call(path = '', options: RequestInit = {}) {
  assertApiConfiguration();
  const response = await fetch(
    new URL(`${apiBaseUrl}/saved-decisions${path}`, window.location.origin),
    {
      ...options,
      headers: apiHeaders(options.body ? { 'Content-Type': 'application/json' } : {}),
    },
  );
  if (!response.ok && !(options.method === 'DELETE' && response.status === 404))
    throw new Error(
      response.status === 401
        ? 'Sua sessão expirou. Entre novamente.'
        : response.status === 404
          ? 'Esta decisão não está mais disponível no acervo.'
          : 'Não foi possível atualizar as decisões salvas. Tente novamente.',
    );
  return response;
}
function readSaved(value: unknown): SavedDecision {
  const item = value as Partial<SavedDecision> | null;
  if (
    !item ||
    typeof item.source !== 'string' ||
    !item.source ||
    typeof item.identifier !== 'string' ||
    !item.identifier ||
    typeof item.court !== 'string' ||
    typeof item.summary !== 'string' ||
    (item.case_number !== null && typeof item.case_number !== 'string') ||
    (item.decided_on !== null && typeof item.decided_on !== 'string') ||
    typeof item.created_at !== 'string' ||
    !Number.isFinite(Date.parse(item.created_at)) ||
    typeof item.available !== 'boolean'
  )
    throw new Error('Não foi possível ler as decisões salvas. Tente novamente.');
  return item as SavedDecision;
}
export async function listSavedDecisions(signal?: AbortSignal): Promise<SavedDecision[]> {
  const body = (await (await call('', { signal })).json()) as { decisions?: unknown };
  if (!Array.isArray(body.decisions))
    throw new Error('Não foi possível ler as decisões salvas. Tente novamente.');
  return body.decisions.map(readSaved);
}
export async function saveDecision(key: DecisionKey): Promise<SavedDecision> {
  return readSaved(await (await call('', { method: 'POST', body: JSON.stringify(key) })).json());
}
export async function removeDecision(key: DecisionKey): Promise<void> {
  await call(`/${encodeURIComponent(key.source)}/${encodeURIComponent(key.identifier)}`, {
    method: 'DELETE',
  });
}
export const bookmarkFailure = (error: unknown) =>
  error instanceof Error
    ? error.message
    : 'Não foi possível atualizar as decisões salvas. Tente novamente.';
