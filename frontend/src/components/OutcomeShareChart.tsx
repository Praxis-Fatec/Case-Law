import type { OutcomeCount } from '../api/indicators';

const drawable = (row: OutcomeCount): row is OutcomeCount & { decisions: number } =>
  row.decisions !== null && row.decisions > 0;

// One bar, split in the order the panel ranked once for the list beside it, so
// the two can never disagree. Lengths are proportional to the counts, over the
// decisions that carry a reading — the same denominator the list states. The
// list carries every number as text, so the drawing is hidden from screen
// readers rather than read twice.
function OutcomeShareChart({ outcomes }: { outcomes: OutcomeCount[] }) {
  const parts = outcomes.filter(drawable);
  const counted = parts.reduce((sum, row) => sum + row.decisions, 0);

  if (!counted) {
    return null;
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
