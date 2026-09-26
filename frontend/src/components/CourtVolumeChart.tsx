import type { CourtVolume } from '../api/indicators';
import { formatCount } from './coverageFormat';
import { axisTicks } from './volumeFormat';

// A court whose count did not come cannot be drawn: it has no length. It stays
// in the composition beside the chart, said as not informed.
const drawable = (court: CourtVolume): court is CourtVolume & { decisions: number } =>
  court.decisions !== null;

// Horizontal bars from one baseline, busiest court first, each with its count
// at the tip. The composition list carries the same numbers as text, so the
// drawing itself is hidden from screen readers rather than read twice.
function CourtVolumeChart({ courts }: { courts: CourtVolume[] }) {
  // Sorted here too, so the order never depends on the answer's.
  const bars = courts
    .filter(drawable)
    .sort((a, b) => b.decisions - a.decisions || a.abbreviation.localeCompare(b.abbreviation));
  const ticks = axisTicks(Math.max(0, ...bars.map((court) => court.decisions)));
  const top = ticks[ticks.length - 1] || 1;
  const at = (value: number) => `${(value / top) * 100}%`;

  return (
    <div className="volume-chart" aria-hidden="true">
      <div className="volume-chart__plot">
        {/* The same span the bars are measured in: past the court labels,
            short of the room kept for the count at the longest bar's tip. */}
        <div className="volume-chart__scale">
          {ticks.map((tick) => (
            <span key={tick} className="volume-chart__grid" style={{ left: at(tick) }} />
          ))}
        </div>

        {bars.map((court) => (
          <div key={court.abbreviation} className="volume-chart__row">
            <span className="volume-chart__label">{court.abbreviation}</span>
            <span className="volume-chart__track">
              <span className="volume-chart__bar" style={{ width: at(court.decisions) }} />
              <span className="volume-chart__value">{formatCount(court.decisions)}</span>
            </span>
          </div>
        ))}
      </div>

      <div className="volume-chart__axis">
        <div className="volume-chart__scale">
          {ticks.map((tick) => (
            <span key={tick} className="volume-chart__tick" style={{ left: at(tick) }}>
              {formatCount(tick)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default CourtVolumeChart;
