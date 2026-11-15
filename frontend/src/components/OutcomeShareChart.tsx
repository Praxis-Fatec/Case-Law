import type { OutcomeCount } from '../api/indicators';
import { outcomeLabel, percent } from './outcomeFormat';
import { axisTicks } from './volumeFormat';
import { formatCount } from './coverageFormat';

const drawable = (row: OutcomeCount): row is OutcomeCount & { decisions: number } =>
  row.decisions !== null && row.decisions > 0;

// One bar, split in the order the panel ranked once for the list beside it, so
// the two can never disagree. Lengths are proportional to the counts, over the
// decisions that carry a reading — the same denominator the list states. The
// list carries every number as text, so the drawing is hidden from screen
// readers rather than read twice.
function OutcomeShareChart({
  outcomes,
  horizontal = false,
  onSelect,
  disabled = false,
  maxValue,
  labelFor = outcomeLabel,
}: {
  outcomes: OutcomeCount[];
  horizontal?: boolean;
  onSelect?: (outcome: string, count: number) => void;
  disabled?: boolean;
  maxValue?: number;
  labelFor?: (value: string) => string;
}) {
  const parts = outcomes.filter(drawable);
  const counted = parts.reduce((sum, row) => sum + row.decisions, 0);

  if (!counted) {
    return null;
  }

  if (horizontal) {
    const ticks = axisTicks(maxValue ?? Math.max(...parts.map((row) => row.decisions)));
    const top = ticks[ticks.length - 1] || 1;
    const Row = onSelect ? 'button' : 'div';
    return (
      <div className="outcome-horizontal">
        {outcomes.map((row) => (
          <Row
            type={onSelect ? 'button' : undefined}
            className="indicator-target indicator-target--outcome outcome-horizontal__row"
            key={row.outcome}
            disabled={onSelect ? disabled || row.decisions === null : undefined}
            aria-label={
              onSelect
                ? `Consultar documentos com resultado ${labelFor(row.outcome)}: ${formatCount(row.decisions)} decisões`
                : undefined
            }
            onClick={() => row.decisions !== null && onSelect?.(row.outcome, row.decisions)}
          >
            <span className="outcome-horizontal__label">{labelFor(row.outcome)}</span>
            <span className="outcome-horizontal__track" aria-hidden="true">
              <span className="outcome-horizontal__grid">
                {ticks.map((tick) => (
                  <span key={tick} style={{ left: `${(tick / top) * 100}%` }} />
                ))}
              </span>
              <span
                className="outcome-horizontal__bar"
                data-outcome={row.outcome}
                style={{ width: `${((row.decisions ?? 0) / top) * 100}%` }}
              />
              <span className="outcome-horizontal__value">
                {row.share === null ? '—' : percent(row.share)}
              </span>
            </span>
            <span className="outcome-list__count">
              {formatCount(row.decisions)}
              <span className="sr-only"> decisões</span>
            </span>
            {row.share !== null && <span className="sr-only"> ({percent(row.share)})</span>}
          </Row>
        ))}
        <div className="outcome-horizontal__axis" aria-hidden="true">
          {ticks.map((tick) => (
            <span key={tick} style={{ left: `${(tick / top) * 100}%` }}>
              {formatCount(tick)}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="outcome-chart" aria-hidden="true">
      {parts.map((row) => (
        <span
          key={row.outcome}
          className="outcome-chart__part"
          data-outcome={row.outcome}
          style={{ width: `${(row.decisions / counted) * 100}%` }}
        />
      ))}
    </div>
  );
}

export default OutcomeShareChart;
