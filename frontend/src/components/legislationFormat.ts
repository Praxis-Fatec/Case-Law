import type { CitedLegislation } from '../api/legislation';

// The act codes whose meaning is settled, and only those. They cover 99,30% of
// the references the collection holds; the other 86 codes reach the screen as
// the code the court wrote.
//
// This list is short on purpose. `CVC` looks like *convenção* and `CNV` looks
// like it too, and writing a guess beside a statute number reads as fact — the
// same class of error as linking to the wrong law. Each entry below was checked
// against the court's own name block in the source: `CFD` rows say
// CONSTITUIÇÃO FEDERAL, `CES` rows name a state's constitution, `RGI` rows name
// a court's internal rules.
export const ACT_LABELS: Record<string, string> = {
  LEI: 'Lei',
  LCP: 'Lei Complementar',
  LDL: 'Lei Delegada',
  DEL: 'Decreto-Lei',
  DEC: 'Decreto',
  DLG: 'Decreto Legislativo',
  MPR: 'Medida Provisória',
  EMC: 'Emenda Constitucional',
  CFB: 'Constituição Federal',
  CFD: 'Constituição Federal',
  CES: 'Constituição Estadual',
  RES: 'Resolução',
  RSF: 'Resolução do Senado Federal',
  PRT: 'Portaria',
  PRV: 'Provimento',
  CIR: 'Circular',
  REC: 'Recomendação',
  CVC: 'Convenção',
  ENU: 'Enunciado',
  RGI: 'Regimento Interno',
  SUM: 'Súmula',
};

// Three of the six spheres have a reading. `MUN`, `INT` and `IES` do not get
// one: calling a municipal statute a state statute is a wrong answer, and
// there is no safe guess for `IES` at all. 0,426% of the collection, shown as
// the court's own code.
export const SPHERE_LABELS: Record<string, string> = {
  EST: 'estadual',
  DIS: 'distrital',
};

// Federal is the default and says nothing: "Lei 13.105/2015" is how a petition
// writes it, and "Lei federal 13.105/2015" is noise on 97,58% of the lines.
const IMPLICIT_SPHERE = 'FED';

const ROMAN: [number, string][] = [
  [1000, 'M'],
  [900, 'CM'],
  [500, 'D'],
  [400, 'CD'],
  [100, 'C'],
  [90, 'XC'],
  [50, 'L'],
  [40, 'XL'],
  [10, 'X'],
  [9, 'IX'],
  [5, 'V'],
  [4, 'IV'],
  [1, 'I'],
];

// Incisos are numbered in arabic in the source and read in roman numerals
// everywhere else. Anything that is not a plain positive number is left as it
// came: 148 of the source's 324.454 item tokens are not numeric, and inventing
// a numeral for them would be inventing the citation.
export function roman(value: string): string {
  const number = Number(value);

  if (!Number.isInteger(number) || number < 1 || number > 3999) {
    return value;
  }

  let rest = number;
  let out = '';
  for (const [size, letters] of ROMAN) {
    while (rest >= size) {
      out += letters;
      rest -= size;
    }
  }
  return out;
}

// "art. 1º" up to nine and "art. 10" from ten: the convention Brazilian legal
// writing uses, and the one a reader checks the citation against. A lettered
// article keeps its hyphen — "art. 543-B" — and never takes the ordinal.
export function articleLabel(article: string): string {
  const plain = /^[0-9]+$/.test(article);
  const number = Number(article);

  if (plain && number >= 1 && number <= 9) {
    return `art. ${number}º`;
  }
  if (plain) {
    return `art. ${number.toLocaleString('pt-BR')}`;
  }
  return `art. ${article}`;
}

export function paragraphLabel(paragraph: string): string {
  if (!/^[0-9]+$/.test(paragraph)) {
    // `único` arrives spelled out, and "§ parágrafo único" is not a thing.
    return paragraph === 'único' ? 'parágrafo único' : paragraph;
  }

  const number = Number(paragraph);
  return number <= 9 ? `§${number}º` : `§${number}`;
}

// "III e IV", "a, b e c": the list separator a petition uses, so the reader
// sees the citation the way they would write it. Every item is shown — showing
// one of two narrows the citation while looking complete.
export function joinParts(parts: string[]): string {
  if (parts.length <= 1) {
    return parts.join('');
  }
  return `${parts.slice(0, -1).join(', ')} e ${parts[parts.length - 1]}`;
}

export const actLabel = (reference: CitedLegislation): string | null =>
  reference.act_type ? (ACT_LABELS[reference.act_type] ?? reference.act_type) : null;

// "Decreto-Lei 3.365/1941". No number is not a missing field: `CFB:******` is
// how the court writes the Constitution, and 30,29% of the references name an
// act that has no number to write.
export function actName(reference: CitedLegislation): string | null {
  const act = actLabel(reference);

  if (!act) {
    return null;
  }

  const sphere =
    reference.sphere && reference.sphere !== IMPLICIT_SPHERE
      ? (SPHERE_LABELS[reference.sphere] ?? `(${reference.sphere})`)
      : null;

  const head = sphere ? `${act} ${sphere}` : act;
  const number = reference.number === null ? null : reference.number.toLocaleString('pt-BR');

  if (number && reference.year) {
    return `${head} ${number}/${reference.year}`;
  }
  if (number) {
    return `${head} ${number}`;
  }
  if (reference.year) {
    return `${head} de ${reference.year}`;
  }
  return head;
}

// Everything after the act: "art. 26, §2º", "art. 105, III, a e c". Empty when
// the decision cited the act without pointing inside it, which is 36,68% of
// the references — the act alone is then the whole citation.
export function articlePath(reference: CitedLegislation): string {
  if (!reference.article) {
    return '';
  }

  const parts = [articleLabel(reference.article)];

  if (reference.paragraphs.length > 0) {
    parts.push(joinParts(reference.paragraphs.map(paragraphLabel)));
  }
  if (reference.items.length > 0) {
    parts.push(joinParts(reference.items.map(roman)));
  }
  if (reference.letters.length > 0) {
    parts.push(joinParts(reference.letters.map((letter) => letter.toLowerCase())));
  }

  return parts.join(', ');
}

// The whole citation, as a petition would write it. Null when the parser read
// no act type: there is nothing to expand, and the court's own text is what the
// screen shows instead.
export function referenceLabel(reference: CitedLegislation): string | null {
  const name = actName(reference);

  if (!name) {
    return null;
  }

  const path = articlePath(reference);
  return path ? `${name}, ${path}` : name;
}
