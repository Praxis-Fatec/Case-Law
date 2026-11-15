import { describe, expect, it } from 'vitest';

import type { CitedLegislation } from '../api/legislation';
import { readCitedLegislation, readCitedLegislationList } from '../api/legislation';
import {
  ACT_LABELS,
  actName,
  articleLabel,
  articlePath,
  joinParts,
  paragraphLabel,
  referenceLabel,
  roman,
} from '../components/legislationFormat';

/**
 * How a reference becomes a citation a lawyer can read.
 *
 * Every case here is a shape the collection actually holds, counted in
 * documentation/architecture/legislative-references.md. The ones that matter
 * most are the ones that come out plausible when read wrong: `543-B` read as
 * five digits is article 5.434, and an act code expanded by guesswork is an
 * invented name sitting beside a real statute number.
 */

const reference = (over: Partial<CitedLegislation> = {}): CitedLegislation => ({
  sphere: 'FED',
  act_type: 'LEI',
  number: 13105,
  year: 2015,
  article: null,
  paragraphs: [],
  items: [],
  letters: [],
  recognised: true,
  raw: 'LEG:FED LEI:013105 ANO:2015',
  ...over,
});

describe('o nome do ato', () => {
  it('escreve o número como uma petição, com separador de milhar', () => {
    expect(actName(reference())).toBe('Lei 13.105/2015');
  });

  it('o ato sem número vem pelo ano, que é como a Constituição é citada', () => {
    expect(actName(reference({ act_type: 'CFB', number: null, year: 1988 }))).toBe(
      'Constituição Federal de 1988',
    );
  });

  it('federal não é dito, porque 97,58% das linhas são federais', () => {
    expect(actName(reference({ sphere: 'FED' }))).toBe('Lei 13.105/2015');
  });

  it('estadual e distrital são ditos', () => {
    expect(actName(reference({ sphere: 'EST', number: 1234, year: 2000 }))).toBe(
      'Lei estadual 1.234/2000',
    );
    expect(actName(reference({ sphere: 'DIS', number: 212, year: 1999 }))).toBe(
      'Lei distrital 212/1999',
    );
  });

  it('a esfera sem leitura segura fica como o código do tribunal', () => {
    // MUN, INT e IES são 0,426% do acervo. Chamar lei municipal de estadual é
    // resposta errada, e para IES não existe palpite honesto.
    expect(actName(reference({ sphere: 'MUN', number: 123, year: 2009 }))).toBe(
      'Lei (MUN) 123/2009',
    );
  });

  it('o código de ato que não está no catálogo aparece como código', () => {
    // 86 dos 106 códigos não têm expansão verificada. Inventar "convênio" para
    // CNV seria escrever um nome falso ao lado de um número verdadeiro.
    expect(ACT_LABELS.CNV).toBeUndefined();
    expect(actName(reference({ act_type: 'CNV', number: 45, year: 1997 }))).toBe('CNV 45/1997');
  });

  it('sem tipo de ato não há nome a escrever', () => {
    expect(actName(reference({ act_type: null }))).toBeNull();
    expect(referenceLabel(reference({ act_type: null }))).toBeNull();
  });
});

describe('o artigo', () => {
  it('até nove vai no ordinal, como se escreve', () => {
    expect(articleLabel('7')).toBe('art. 7º');
  });

  it('de dez em diante vai no cardinal, com milhar', () => {
    expect(articleLabel('10')).toBe('art. 10');
    expect(articleLabel('1025')).toBe('art. 1.025');
  });

  it('o artigo com letra mantém o hífen e não ganha ordinal', () => {
    // 24.222 tokens são desta forma. Lido como cinco dígitos, 543-B viraria o
    // artigo 5.434: número plausível, de artigo que não foi citado.
    expect(articleLabel('543-B')).toBe('art. 543-B');
    expect(articleLabel('1-F')).toBe('art. 1-F');
  });
});

describe('o que vem dentro do artigo', () => {
  it('o parágrafo até nove é ordinal', () => {
    expect(paragraphLabel('2')).toBe('§2º');
    expect(paragraphLabel('11')).toBe('§11');
  });

  it('parágrafo único é dito por extenso', () => {
    expect(paragraphLabel('único')).toBe('parágrafo único');
  });

  it('o inciso é lido em romano', () => {
    expect(roman('3')).toBe('III');
    expect(roman('9')).toBe('IX');
    expect(roman('44')).toBe('XLIV');
  });

  it('o inciso que não é número fica como veio', () => {
    // 148 dos 324.454 tokens de inciso não são numéricos.
    expect(roman('A')).toBe('A');
    expect(roman('')).toBe('');
  });

  it('todos os itens aparecem, nunca só o primeiro', () => {
    // 2,49% dos segmentos nomeiam mais de um inciso. Mostrar um de dois
    // estreita a citação e parece completo.
    expect(joinParts(['III', 'IV'])).toBe('III e IV');
    expect(joinParts(['a', 'b', 'c'])).toBe('a, b e c');
  });

  it('o caminho inteiro sai na ordem em que se lê', () => {
    expect(
      articlePath(
        reference({ article: '105', paragraphs: ['2'], items: ['3', '4'], letters: ['A'] }),
      ),
    ).toBe('art. 105, §2º, III e IV, a');
  });

  it('sem artigo, o ato é a citação inteira', () => {
    // 36,68% das referências citam a lei sem apontar dentro dela.
    expect(articlePath(reference())).toBe('');
    expect(referenceLabel(reference())).toBe('Lei 13.105/2015');
  });
});

describe('a leitura da resposta da API', () => {
  it('monta a referência com os campos que vieram', () => {
    const lida = readCitedLegislation({
      sphere: 'FED',
      act_type: 'DEL',
      number: 3365,
      year: 1941,
      article: '26',
      paragraphs: ['2'],
      items: [],
      letters: [],
      recognised: true,
      raw: 'LEG:FED DEL:003365 ANO:1941 ART:00026 PAR:00002',
    });

    expect(lida && referenceLabel(lida)).toBe('Decreto-Lei 3.365/1941, art. 26, §2º');
  });

  it('`recognised` ausente é tratado como não reconhecido', () => {
    // O lado cauteloso: mostra o texto do tribunal em vez de afirmar uma
    // leitura que não houve.
    expect(readCitedLegislation({ raw: 'LEG:FED' })?.recognised).toBe(false);
  });

  it('a entrada sem ato e sem texto não vira linha em branco', () => {
    expect(readCitedLegislation({})).toBeNull();
    expect(readCitedLegislationList({ results: [{}, {}] })).toEqual([]);
  });

  it('um corpo sem `results` é lista vazia, não erro', () => {
    expect(readCitedLegislationList(null)).toEqual([]);
    expect(readCitedLegislationList({ results: 'nada' })).toEqual([]);
  });
});
