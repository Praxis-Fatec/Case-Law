import type { SearchDecisionMatch } from '../api/search';

type DecisionCardData = Pick<
  SearchDecisionMatch,
  'court' | 'case_number' | 'judging_body' | 'reporting_judge' | 'decided_on' | 'snippet'
> & {
  published_on?: string | null;
};

type DecisionResultCardProps = {
  decision: DecisionCardData;
};

function normalizeText(value: string | null | undefined): string {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

function getDisplayValue(value: string | null | undefined): string {
  const normalized = normalizeText(value);
  return normalized || 'Não informado';
}

function stripHtml(value: string | null | undefined): string {
  if (typeof value !== 'string') {
    return '';
  }

  const fallback = value.replace(/<[^>]+>/g, ' ');
  const parser = document.createElement('textarea');
  parser.innerHTML = fallback;

  return parser.value.replace(/\s+/g, ' ').trim();
}

function formatDate(value: string | null | undefined): string | null {
  const normalized = normalizeText(value);

  if (!normalized) {
    return null;
  }

  const isoDateMatch = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);

  if (isoDateMatch) {
    const [, year, month, day] = isoDateMatch;
    const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));

    if (Number.isNaN(date.getTime())) {
      return null;
    }

    return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
  }

  const parsedDate = new Date(normalized);

  if (Number.isNaN(parsedDate.getTime())) {
    return null;
  }

  return parsedDate.toLocaleDateString('pt-BR', { timeZone: 'UTC' });
}

function DecisionResultCard({ decision }: DecisionResultCardProps) {
  const snippetText = stripHtml(decision.snippet);
  const metadata = [
    { label: 'Processo', value: getDisplayValue(decision.case_number) },
    { label: 'Órgão julgador', value: getDisplayValue(decision.judging_body) },
    { label: 'Relator', value: getDisplayValue(decision.reporting_judge) },
    {
      label: 'Data de julgamento',
      value: formatDate(decision.decided_on) ?? 'Não informado',
    },
    {
      label: 'Data de publicação',
      value: formatDate(decision.published_on) ?? 'Não informado',
    },
  ];

  return (
    <article
      className="decision-result-card"
      aria-label={`Decisão ${decision.case_number ?? 'sem processo'}`}
    >
      <header className="decision-result-card__header">
        <div className="decision-result-card__title">
          <span className="decision-result-card__court">{getDisplayValue(decision.court)}</span>
          <span className="decision-result-card__separator">•</span>
          <span className="decision-result-card__process">{getDisplayValue(decision.case_number)}</span>
        </div>
      </header>

      <div className="decision-result-card__content">
        <p className="decision-result-card__snippet">
          {snippetText || 'Trecho indisponível.'}
        </p>
      </div>

      <dl className="decision-result-card__meta">
        {metadata.map((item) => (
          <div className="decision-result-card__meta-item" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export default DecisionResultCard;
