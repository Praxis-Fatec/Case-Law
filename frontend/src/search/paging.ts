// What a page of results says about itself: which page, of what size, where it
// sits in the total and how many it carried. Read from the API's answer, never
// guessed, and only once that answer has arrived.
export type PageInfo = {
  page: number;
  pageSize: number;
  total: number;
  count: number;
  rangeFrom?: number | null;
  rangeTo?: number | null;
};

export type PagePosition = {
  // Null when the page carries nothing: there is no slice to name.
  from: number | null;
  to: number | null;
  total: number;
  hasPrevious: boolean;
  hasNext: boolean;
};

// The API's own range when it sends one. An API published before paging was
// stable does not, and then the range is worked out the way the API works it
// out — offset = (page - 1) * page_size — from what this answer carried, so it
// is never more than the page received nor past the total.
export function positionOf(info: PageInfo): PagePosition {
  const offset = (info.page - 1) * info.pageSize;
  const carried = info.count > 0;

  const from = info.rangeFrom ?? (carried ? offset + 1 : null);
  const to =
    info.rangeTo ?? (carried && from !== null ? Math.min(from + info.count - 1, info.total) : null);

  return {
    from,
    to,
    total: info.total,
    // A page past the end — the data changed since — still has a way back.
    hasPrevious: info.page > 1,
    hasNext: to !== null && to < info.total,
  };
}

const number = new Intl.NumberFormat('pt-BR');

export function describePosition(position: PagePosition): string {
  if (position.total === 0) {
    return 'Nenhum resultado encontrado';
  }
  if (position.from === null || position.to === null) {
    return `Esta página não tem mais resultados de ${number.format(position.total)}`;
  }
  const noun = position.total === 1 ? 'resultado' : 'resultados';
  return `Exibindo ${number.format(position.from)}–${number.format(position.to)} de ${number.format(position.total)} ${noun}`;
}

// How many pages a result has, from the API's own total and page size; one at
// least, so an empty result still has the page it is on.
export function lastPageOf(info: PageInfo): number {
  return Math.max(1, Math.ceil(info.total / info.pageSize));
}

// How many numbered places the row holds, the gaps included, so it keeps one
// width wherever the reader is and the arrows never move under the pointer.
const SLOTS = 7;

export type PageSlot = number | 'gap-start' | 'gap-end';

// The first and the last page always, the current one with its neighbours,
// and a gap for what lies between: 1 2 3 4 5 … 60, 1 … 29 30 31 … 60.
export function pageSlots(current: number, last: number): PageSlot[] {
  if (last <= SLOTS) {
    return Array.from({ length: last }, (_, index) => index + 1);
  }
  const range = (from: number, to: number) =>
    Array.from({ length: to - from + 1 }, (_, index) => from + index);

  if (current <= SLOTS - 3) {
    return [...range(1, SLOTS - 2), 'gap-end', last];
  }
  if (current >= last - (SLOTS - 4)) {
    return [1, 'gap-start', ...range(last - (SLOTS - 3), last)];
  }
  return [1, 'gap-start', current - 1, current, current + 1, 'gap-end', last];
}
