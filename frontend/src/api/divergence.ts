import { assertApiConfiguration } from './client';
import { cutUrl, type VolumeParams } from './indicators';
import { apiHeaders } from './token';
import { readDetail, SearchRequestError } from './search';

export type DivergenceCounts = { denied: number; granted: number; partially_granted: number };
export type DivergencePanelNumbers = {
  court: string;
  class_code: number | null;
  panel: string | null;
  documents: number;
  classified_documents: number;
  unknown_documents: number;
  outcomes: DivergenceCounts;
  processes: number;
  missing_process_documents: number;
  repeated_documents: number;
};
export type DivergenceSample = {
  panel: string;
  processes: number;
  classified: number;
  unknown: number;
  coverage: number | null;
  outcomes: DivergenceCounts;
  shared_processes_excluded: number;
  missing_process_documents: number;
  repeated_documents: number;
};
export type DivergencePair = {
  court: string;
  class_code: number;
  left: DivergenceSample;
  right: DivergenceSample;
  reason: string;
  signal: boolean;
  adjusted_p: number | null;
  raw_p: number | null;
  effect: number | null;
};
export type Divergence = {
  rule_version: string;
  documents: number;
  tested_pairs: number;
  thresholds: {
    minimum_classified_processes: number;
    minimum_classification_coverage: number;
    minimum_expected_cell: number;
    alpha: number;
    minimum_effect: number;
  };
  panels: DivergencePanelNumbers[];
  pairs: DivergencePair[];
};

const invalid = () =>
  new Error('A análise das turmas retornou dados incompletos ou incompatíveis. Tente novamente.');
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalid();
  return value as Record<string, unknown>;
}
function number(value: unknown, fraction = false): number {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value) ||
    value < 0 ||
    (fraction ? value > 1 : !Number.isSafeInteger(value))
  )
    throw invalid();
  return value;
}
const nullableFraction = (value: unknown) => (value === null ? null : number(value, true));
function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw invalid();
  return value;
}
function counts(value: unknown): DivergenceCounts {
  const row = object(value);
  return {
    denied: number(row.denied),
    granted: number(row.granted),
    partially_granted: number(row.partially_granted),
  };
}
const total = (values: DivergenceCounts) =>
  values.denied + values.granted + values.partially_granted;
function sample(value: unknown): DivergenceSample {
  const row = object(value);
  const answer = {
    panel: text(row.panel),
    processes: number(row.processes),
    classified: number(row.classified),
    unknown: number(row.unknown),
    coverage: nullableFraction(row.coverage),
    outcomes: counts(row.outcomes),
    shared_processes_excluded: number(row.shared_processes_excluded),
    missing_process_documents: number(row.missing_process_documents),
    repeated_documents: number(row.repeated_documents),
  };
  if (
    answer.classified + answer.unknown !== answer.processes ||
    total(answer.outcomes) !== answer.classified ||
    (answer.processes === 0
      ? answer.coverage !== null
      : answer.coverage === null ||
        Math.abs(answer.coverage - answer.classified / answer.processes) > 1e-10)
  )
    throw invalid();
  return answer;
}

export function readDivergence(value: unknown): Divergence {
  const body = object(value);
  if (body.rule_version !== 'RF22-v1' || !Array.isArray(body.panels) || !Array.isArray(body.pairs))
    throw invalid();
  const thresholds = object(body.thresholds);
  const answer: Divergence = {
    rule_version: body.rule_version,
    documents: number(body.documents),
    tested_pairs: number(body.tested_pairs),
    thresholds: {
      minimum_classified_processes: number(thresholds.minimum_classified_processes),
      minimum_classification_coverage: number(thresholds.minimum_classification_coverage, true),
      minimum_expected_cell: number(thresholds.minimum_expected_cell),
      alpha: number(thresholds.alpha, true),
      minimum_effect: number(thresholds.minimum_effect, true),
    },
    panels: body.panels.map((value) => {
      const row = object(value);
      const panel: DivergencePanelNumbers = {
        court: text(row.court),
        class_code: row.class_code === null ? null : number(row.class_code),
        panel: row.panel === null ? null : text(row.panel),
        documents: number(row.documents),
        classified_documents: number(row.classified_documents),
        unknown_documents: number(row.unknown_documents),
        outcomes: counts(row.outcomes),
        processes: number(row.processes),
        missing_process_documents: number(row.missing_process_documents),
        repeated_documents: number(row.repeated_documents),
      };
      if (
        total(panel.outcomes) !== panel.classified_documents ||
        panel.classified_documents + panel.unknown_documents !== panel.documents
      )
        throw invalid();
      return panel;
    }),
    pairs: body.pairs.map((value) => {
      const row = object(value);
      if (typeof row.signal !== 'boolean') throw invalid();
      return {
        court: text(row.court),
        class_code: number(row.class_code),
        left: sample(row.left),
        right: sample(row.right),
        reason: text(row.reason),
        signal: row.signal,
        adjusted_p: nullableFraction(row.adjusted_p),
        raw_p: nullableFraction(row.raw_p),
        effect: nullableFraction(row.effect),
      };
    }),
  };
  // A malformed signal cannot turn a failed gate into a highlighted finding.
  for (const pair of answer.pairs) {
    if (
      pair.signal &&
      (pair.reason !== 'difference' ||
        pair.adjusted_p === null ||
        pair.raw_p === null ||
        pair.effect === null ||
        pair.adjusted_p > answer.thresholds.alpha ||
        pair.effect < answer.thresholds.minimum_effect ||
        [pair.left, pair.right].some(
          (sample) =>
            sample.classified < answer.thresholds.minimum_classified_processes ||
            sample.coverage === null ||
            sample.coverage < answer.thresholds.minimum_classification_coverage,
        ))
    )
      throw invalid();
  }
  if (answer.panels.reduce((sum, panel) => sum + panel.documents, 0) !== answer.documents)
    throw invalid();
  return answer;
}

export async function getDivergence(
  params: VolumeParams,
  options: { signal?: AbortSignal } = {},
): Promise<Divergence> {
  assertApiConfiguration();
  const response = await fetch(cutUrl('/indicators/divergence', params).toString(), {
    method: 'GET',
    headers: apiHeaders(),
    signal: options.signal,
  });
  if (!response.ok) throw new SearchRequestError(response.status, await readDetail(response));
  return readDivergence(await response.json());
}
