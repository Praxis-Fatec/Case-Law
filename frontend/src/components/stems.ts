/**
 * Turning a stem back into the word that produced it.
 *
 * PostgreSQL stems as it indexes, so what matched is a stem and not a word:
 * `poluidor-pag` of *poluidor-pagador*, `litiganc` of *litigância*. The stem
 * is the honest record of the match and belongs in the data; on a screen it
 * says nothing. The translation back is presentation work, and it is shared by
 * every block that has to explain why it is suggesting something.
 */

export const WORDS = /[^\p{L}\p{N}-]+/u;

export const strip = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

export function splitWords(value: string): string[] {
  return strip(value).split(WORDS).filter(Boolean);
}

// The stemmer truncates, so a stem is a prefix of the word it came from once
// the accents are gone.
export function carries(text: string, stems: string[]): boolean {
  const parts = splitWords(text);
  return stems.some((stem) => parts.some((word) => word.startsWith(stem)));
}

const EDGES = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;

/**
 * Each stem as the text spells it, in the order the stems arrived.
 *
 * The order is the API's — rarest first — because that is the order that
 * matters to a reader deciding whether to open the thing. A stem the text does
 * not carry is left out rather than shown raw.
 */
export function spell(text: string, stems: string[], limit: number): string[] {
  const written = text.split(WORDS).filter(Boolean);
  const spelled: string[] = [];
  const seen = new Set<string>();

  for (const stem of stems) {
    if (spelled.length >= limit) {
      break;
    }

    const found = written.find((word) => strip(word).startsWith(stem));
    const word = found?.replace(EDGES, '') ?? '';
    const plain = strip(word);

    if (!word || seen.has(plain)) {
      continue;
    }

    seen.add(plain);
    spelled.push(word);
  }

  return spelled;
}
