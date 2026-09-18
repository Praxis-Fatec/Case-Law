INSERT INTO core.decisao (
    fonte_codigo, identificador_fonte, tribunal_sigla, processo,
    orgao_julgador, relator, classe_cnj, data_julgamento, data_publicacao,
    data_referencia, ementa, tipo_texto, decisao_texto,
    turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
)
VALUES
(
    'tjdft-jurisdf', '1000001', 'TJDFT', '0700001-11.2026.8.07.0001',
    '1ª TURMA CÍVEL', 'ANA CANTARINO', 198, '2026-03-10', '2026-03-15',
    '2026-03-10',
    'DIREITO DO CONSUMIDOR. Inscrição indevida em cadastro de inadimplentes. '
    'Dano moral in re ipsa. Ação procedente. Recurso não provido.',
    'ementa_completa', 'RECURSO NÃO PROVIDO. UNÂNIME.',
    FALSE, TRUE, 'https://jurisdf.tjdft.jus.br/detalhes/1000001',
    TO_TSVECTOR('portugues_sem_acento',
        'DIREITO DO CONSUMIDOR. Inscrição indevida em cadastro de inadimplentes. '
        'Dano moral in re ipsa. Ação procedente. Recurso não provido.')
),
(
    'tjdft-jurisdf', '1000002', 'TJDFT', '0700002-22.2026.8.07.0001',
    'CÂMARA CRIMINAL', 'DEMETRIUS GOMES CAVALCANTI', 417, '2026-04-20', '2026-04-25',
    '2026-04-20',
    'PENAL. Usucapião extraordinário não se confunde com posse precária. '
    'Sentença mantida por seus próprios fundamentos.',
    'ementa_completa', 'APELAÇÃO CONHECIDA E DESPROVIDA.',
    FALSE, FALSE, 'https://jurisdf.tjdft.jus.br/detalhes/1000002',
    TO_TSVECTOR('portugues_sem_acento',
        'PENAL. Usucapião extraordinário não se confunde com posse precária. '
        'Sentença mantida por seus próprios fundamentos.')
),
(
    'tjdft-jurisdf', '1000003', 'TJDFT', '0700003-33.2026.8.07.0001',
    '2ª TURMA RECURSAL', 'ALFEU MACHADO', 460, '2026-05-05', '2026-05-09',
    '2026-05-05',
    'CIVIL. Responsabilidade civil por falha na prestação de serviço. '
    'Dano moral configurado. Danos materiais afastados.',
    'ementa_completa', 'RECURSO PARCIALMENTE PROVIDO.',
    TRUE, TRUE, 'https://jurisdf.tjdft.jus.br/detalhes/1000003',
    TO_TSVECTOR('portugues_sem_acento',
        'CIVIL. Responsabilidade civil por falha na prestação de serviço. '
        'Dano moral configurado. Danos materiais afastados.')
);
