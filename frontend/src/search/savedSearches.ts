import { DEFAULT_ORDER, type SearchOrder, type SearchParams } from '../api/search';
import type { SavedSearch } from '../api/savedSearches';
import { hasErrors, rangeErrors, type SearchFilterValues } from './filters';

export const SAVED_SEARCHES_PATH = '/salvas';
export const SAVED_SEARCHES_TRIGGER = 'open-saved-searches';
export class SavedSearchResumeError extends Error {
  constructor() {
    super(
      'Esta pesquisa contém filtros incompatíveis com esta versão. Revise a pesquisa antes de retomá-la.',
    );
    this.name = 'SavedSearchResumeError';
  }
}
export type AdditionalSavedFilters = Pick<
  SearchParams,
  'resultado' | 'orgao_julgador_excluido' | 'relator_excluido'
>;
export type ResumedSearch = {
  q: string;
  filters: SearchFilterValues;
  order: SearchOrder;
  page: number;
  extraFilters?: AdditionalSavedFilters;
};

const supported = new Set([
  'q',
  'tribunal',
  'orgao_julgador',
  'relator',
  'classe_cnj',
  'resultado',
  'orgao_julgador_excluido',
  'relator_excluido',
  'date_from',
  'date_to',
  'published_from',
  'published_to',
  'order',
  'page',
  'page_size',
  'highlight',
]);

export function resumeSavedSearch(saved: SavedSearch): ResumedSearch {
  const values = saved.filters;
  const incompatible = () => new SavedSearchResumeError();
  if (
    Object.keys(values).some((key) => !supported.has(key)) ||
    typeof values.q !== 'string' ||
    values.q.trim().length < 2
  )
    throw incompatible();
  const strings = (key: string): string[] => {
    const value = values[key];
    if (value == null) return [];
    if (!Array.isArray(value) || !value.every((item) => typeof item === 'string'))
      throw incompatible();
    return [...value];
  };
  const date = (key: string): string => {
    const value = values[key];
    if (value == null || value === '') return '';
    if (
      typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
      !Number.isFinite(Date.parse(value)) ||
      new Date(value).toISOString().slice(0, 10) !== value
    )
      throw incompatible();
    return value;
  };
  const classes = values.classe_cnj ?? [];
  if (
    !Array.isArray(classes) ||
    !classes.every((item) => typeof item === 'number' && Number.isInteger(item))
  )
    throw incompatible();
  const order = values.order ?? DEFAULT_ORDER;
  if (order !== 'date' && order !== 'relevance') throw incompatible();
  const filters: SearchFilterValues = {
    courts: strings('tribunal'),
    judgingBodies: strings('orgao_julgador'),
    reportingJudges: strings('relator'),
    proceduralClasses: [...classes],
    dateFrom: date('date_from'),
    dateTo: date('date_to'),
    publishedFrom: date('published_from'),
    publishedTo: date('published_to'),
  };
  if (hasErrors(rangeErrors(filters))) throw incompatible();
  const extraFilters: AdditionalSavedFilters = {};
  for (const key of ['resultado', 'orgao_julgador_excluido', 'relator_excluido'] as const) {
    const items = strings(key);
    if (items.length) extraFilters[key] = items;
  }
  return { q: values.q, filters, order, page: 1, extraFilters };
}
