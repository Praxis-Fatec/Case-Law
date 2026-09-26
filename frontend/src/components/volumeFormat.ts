import type { LastUpdate, VolumeByCourt } from '../api/indicators';

// What the panorama has to show. `idle` is before any search: there is no cut
// to count yet. Until the cut is counted, no bar and no number is shown — never
// a zero that could be read as the answer.
export type VolumeState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'unavailable' }
  | { status: 'loaded'; volume: VolumeByCourt };

// The base's freshness, asked on its own: the volume does not carry it.
export type LastUpdateState =
  { status: 'loading' } | { status: 'unavailable' } | { status: 'loaded'; lastUpdate: LastUpdate };

const STEPS = [1, 2, 2.5, 5];

// Clean ticks from zero to a round number at or above the largest count: 0 / 1
// / 2 / 3 / 4, or 0 / 5.000 / 10.000 / 15.000. Counts are whole, so a step is
// never below one.
export function axisTicks(largest: number): number[] {
  if (!(largest > 0)) {
    return [0];
  }

  const rough = largest / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  // A step of 2,5 only where it lands on whole numbers (25, 250…), never 2,5.
  const multiple =
    STEPS.find((s) => s * magnitude >= rough && Number.isInteger(s * magnitude)) ?? 10;
  const step = Math.max(1, Math.round(multiple * magnitude));
  const top = Math.ceil(largest / step) * step;

  const ticks: number[] = [];
  for (let tick = 0; tick <= top; tick += step) {
    ticks.push(tick);
  }
  return ticks;
}
