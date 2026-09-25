import { describe, expect, it } from 'vitest';

import { describePosition, positionOf } from '../search/paging';

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
