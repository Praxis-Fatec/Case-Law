const DEFAULT_API_URL = 'http://localhost:8000';

const normalizeApiBaseUrl = (value: string | undefined) =>
  (value ?? DEFAULT_API_URL).trim().replace(/\/+$/, '');

export const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL as string | undefined);

export async function fetchHealth() {
  const response = await fetch(`${apiBaseUrl}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json();
}
