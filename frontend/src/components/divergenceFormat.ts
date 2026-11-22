import type { Divergence } from '../api/divergence';

export type DivergenceState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; divergence: Divergence };

export const DIVERGENCE_REASONS: Record<string, string> = {
  unvalidated_group:
    'Sem conclusão: competência comparável ainda não validada para este tribunal, classe e período.',
  ambiguous_group: 'Sem conclusão: há validações de competência sobrepostas.',
  outcome_filter: 'Sem conclusão: remova o filtro de resultado para comparar as distribuições.',
  insufficient_sample: 'Amostra insuficiente para uma conclusão estatística.',
  insufficient_coverage: 'Sem conclusão: cobertura de classificação insuficiente.',
  no_variation: 'Sem variação de resultado para testar.',
  sparse_categories: 'Sem conclusão: categorias com poucos registros para o teste.',
  not_significant:
    'Sem evidência estatística suficiente neste recorte. Isso não comprova equivalência entre as turmas.',
  small_effect: 'Diferença abaixo do limiar prático; sem sinal de divergência.',
  difference: 'Diferença estatística na distribuição dos resultados',
};
