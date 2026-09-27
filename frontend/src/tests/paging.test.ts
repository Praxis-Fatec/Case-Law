import { describe, expect, it } from 'vitest';

import { describePosition, lastPageOf, pageSlots, positionOf } from '../search/paging';

// An API published before paging was stable sends no range: the screen works it
// out the way the API does, from the page it received.
describe('the range without the API range', () => {
  const at = (page: number, count: number, total: number) =>
    describePosition(positionOf({ page, pageSize: 20, total, count }));

  it('goes 1–20, 21–40, 41–45 over 45 matches', () => {
    expect(at(1, 20, 45)).toBe('Exibindo 1–20 de 45 resultados');
    expect(at(2, 20, 45)).toBe('Exibindo 21–40 de 45 resultados');
    expect(at(3, 5, 45)).toBe('Exibindo 41–45 de 45 resultados');
  });

  it('never ends past the total, nor offers a page after it', () => {
    const position = positionOf({ page: 2, pageSize: 20, total: 40, count: 20 });

    expect(position.to).toBe(40);
    expect(position.hasNext).toBe(false);
  });

  it('names no slice for nothing found, or for a page past the end', () => {
    expect(at(1, 0, 0)).toBe('Nenhum resultado encontrado');
    expect(positionOf({ page: 3, pageSize: 20, total: 45, count: 0 })).toMatchObject({
      from: null,
      to: null,
      hasPrevious: true,
      hasNext: false,
    });
  });

  it('reads large totals the Brazilian way', () => {
    expect(at(2, 20, 107828)).toBe('Exibindo 21–40 de 107.828 resultados');
  });
});

describe('the range the API sends', () => {
  it('is used as it comes', () => {
    const position = positionOf({
      page: 3,
      pageSize: 20,
      total: 45,
      count: 5,
      rangeFrom: 41,
      rangeTo: 45,
    });

    expect(describePosition(position)).toBe('Exibindo 41–45 de 45 resultados');
  });
});

// The row of numbers keeps seven places wherever the reader is: the first and
// last pages always, the current one with its neighbours, gaps between.
describe('the numbered pages', () => {
  it('shows every page when there are seven or fewer', () => {
    expect(pageSlots(1, 1)).toEqual([1]);
    expect(pageSlots(3, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('near the start, the first five, a gap and the last', () => {
    expect(pageSlots(1, 60)).toEqual([1, 2, 3, 4, 5, 'gap-end', 60]);
    expect(pageSlots(4, 60)).toEqual([1, 2, 3, 4, 5, 'gap-end', 60]);
  });

  it('in the middle, the current one between its neighbours, a gap either side', () => {
    expect(pageSlots(30, 60)).toEqual([1, 'gap-start', 29, 30, 31, 'gap-end', 60]);
  });

  it('near the end, the first, a gap and the last five', () => {
    expect(pageSlots(57, 60)).toEqual([1, 'gap-start', 56, 57, 58, 59, 60]);
    expect(pageSlots(60, 60)).toEqual([1, 'gap-start', 56, 57, 58, 59, 60]);
  });

  it('counts the pages from the total and page size, one at least', () => {
    expect(lastPageOf({ page: 1, pageSize: 6, total: 356, count: 6 })).toBe(60);
    expect(lastPageOf({ page: 1, pageSize: 6, total: 12, count: 6 })).toBe(2);
    expect(lastPageOf({ page: 1, pageSize: 6, total: 0, count: 0 })).toBe(1);
  });
});
