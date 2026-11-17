type CourtInstance = 'second' | 'superior' | 'supreme';

// Court level is not the same as jurisdiction (federal, state, electoral…).
// Only classify known abbreviations; an unknown court is not evidence of a
// different instance. Reference: CNJ, "Panorama e Estrutura do Poder Judiciário Brasileiro".
// https://www.cnj.jus.br/poder-judiciario/panorama-e-estrutura-do-poder-judiciario-brasileiro/
const SECOND_INSTANCE = new Set([
  'TJAC',
  'TJAL',
  'TJAP',
  'TJAM',
  'TJBA',
  'TJCE',
  'TJDFT',
  'TJES',
  'TJGO',
  'TJMA',
  'TJMT',
  'TJMS',
  'TJMG',
  'TJPA',
  'TJPB',
  'TJPR',
  'TJPE',
  'TJPI',
  'TJRJ',
  'TJRN',
  'TJRS',
  'TJRO',
  'TJRR',
  'TJSC',
  'TJSP',
  'TJSE',
  'TJTO',
  'TRF1',
  'TRF2',
  'TRF3',
  'TRF4',
  'TRF5',
  'TRF6',
]);
const SUPERIOR = new Set(['STJ', 'TST', 'TSE', 'STM']);

function courtInstance(abbreviation: string): CourtInstance | null {
  const court = abbreviation.trim().toUpperCase();
  if (court === 'STF') return 'supreme';
  if (SUPERIOR.has(court)) return 'superior';
  if (SECOND_INSTANCE.has(court)) return 'second';
  return null;
}

export function haveDifferentInstances(left: string, right: string): boolean {
  const leftInstance = courtInstance(left);
  const rightInstance = courtInstance(right);
  return leftInstance !== null && rightInstance !== null && leftInstance !== rightInstance;
}
