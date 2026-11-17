import { describe, expect, it } from 'vitest';
import { haveDifferentInstances } from '../components/courtInstance';

describe('court instances', () => {
  it.each([
    ['STJ', 'TJDFT'],
    ['TJDFT', 'STJ'],
    ['STJ', 'TRF3'],
    ['STF', 'TJSP'],
    ['STF', 'STJ'],
  ])('recognizes different levels for %s and %s', (left, right) => {
    expect(haveDifferentInstances(left, right)).toBe(true);
  });

  it.each([
    ['TJSP', 'TJMG'],
    ['TJDFT', 'TRF3'],
    ['TRF1', 'TRF6'],
    ['STJ', 'TST'],
    ['TSE', 'STM'],
    ['STJ', 'STJ'],
    ['TJDFT', 'TJDFT'],
  ])(
    'does not confuse different courts or jurisdictions with different levels: %s / %s',
    (left, right) => {
      expect(haveDifferentInstances(left, right)).toBe(false);
    },
  );

  it.each([
    ['', 'STJ'],
    ['STJ', ''],
    ['UNKNOWN', 'STJ'],
    ['TJSP', 'UNKNOWN'],
    ['TRF99', 'STJ'],
    ['TJSJ', 'STJ'],
  ])('does not invent a level for missing or unknown courts: %s / %s', (left, right) => {
    expect(haveDifferentInstances(left, right)).toBe(false);
  });

  it('normalizes the abbreviation only for classification', () => {
    expect(haveDifferentInstances(' stj ', 'tjdft')).toBe(true);
    expect(haveDifferentInstances(' tjSp ', 'trf3')).toBe(false);
  });
});
