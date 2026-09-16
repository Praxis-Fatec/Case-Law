# Processo de testes

Este documento descreve a entrega de testes do Case-Law e como ela se conecta
ao fluxo de DevOps. O escopo acompanha o estado atual do projeto: a aplicação
possui uma API FastAPI inicial, com configuração baseada em ambiente e o
endpoint operacional `/health`. Não foram criadas regras de negócio fictícias
apenas para aumentar a quantidade de testes.

## Objetivo e escopo

Os testes protegem dois pontos que já são importantes para o sistema:

| Alvo | Por que foi escolhido | Tipo |
| --- | --- | --- |
| `backend/app/config.py` | Converte `CORS_ORIGINS` em uma lista e define valores padrão. Uma alteração incorreta pode impedir a comunicação com o frontend. | Unitário |
| `backend/app/api/health.py` e `backend/app/main.py` | O endpoint é usado pelo healthcheck do Docker e pelo deploy para decidir se a aplicação está saudável. | Integração |

Infraestrutura externa, como PostgreSQL, não é necessária para esses cenários.
Ela será coberta quando surgirem funcionalidades que realmente consultem o
banco. Testar apenas a infraestrutura não comprovaria uma regra da aplicação.

## Estratégia

Cada cenário segue a estrutura **Given / When / Then**:

1. **Given (Dado):** prepara a configuração ou o cliente HTTP.
2. **When (Quando):** executa a função ou faz uma requisição.
3. **Then (Então):** verifica o resultado observável.

Os testes unitários de `test_config.py` isolam o comportamento de configuração
e usam `monkeypatch` para simular variáveis de ambiente sem alterar a máquina
ou um arquivo `.env` real. Não há dependências externas a mockar nesse módulo.

Os testes de `test_health.py` usam `fastapi.testclient.TestClient` para passar
pelo roteamento, middleware CORS e serialização da resposta. Por isso são
testes de integração: mesmo sem subir um servidor ou PostgreSQL, mais de um
componente da aplicação participa do cenário.

## Cenários implementados

### Unitários

- usa o frontend local quando `CORS_ORIGINS` não foi definido;
- aceita uma única origem;
- separa múltiplas origens por vírgula e remove espaços;
- lê `ENVIRONMENT` do ambiente.

### Integração

- `/health` responde HTTP 200 e `status=ok`;
- `/health` informa o ambiente configurado;
- `/openapi.json` publica o endpoint;
- uma origem autorizada recebe o cabeçalho CORS;
- uma origem desconhecida não recebe autorização CORS;
- o preflight HTTP OPTIONS é respondido.

## Como executar

Na raiz do repositório:

```bash
cd backend
uv sync --locked
uv run pytest
```

Para demonstrar cada camada separadamente:

```bash
uv run pytest -m unit -v
uv run pytest -m integration -v
```

Os mesmos comandos de qualidade usados localmente são executados pelo workflow
existente em `.github/workflows/ci.yml`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run pytest
```

Assim, esta entrega não implementa o CI: ela fornece testes determinísticos,
com dependências declaradas e um comando de saída diferente de zero quando um
comportamento esperado deixa de funcionar. O integrante responsável pelo CI
pode chamar exatamente `uv run pytest` no pipeline.

## Resultado e fluxo de DevOps

O resultado esperado de uma execução correta é **10 testes aprovados**:
4 unitários e 6 de integração. Uma falha deve bloquear a revisão da alteração:
o desenvolvedor investiga o cenário, corrige o código ou o teste, executa
novamente e só então solicita o merge. O pull request deve registrar o que foi
testado e o resultado do comando.

O fluxo fica:

```text
Alteração de código
        ↓
Testes unitários e de integração locais
        ↓
Pull request
        ↓
CI executa lint, tipos e pytest
        ↓
Revisão baseada no resultado
        ↓
Merge e entrega
```

Cobertura é um indicador de alcance, não uma prova de qualidade perfeita:
um teste pode executar uma linha e ainda verificar uma expectativa fraca.
Por isso a seleção dos cenários considera risco e comportamento observável,
e não apenas o percentual de linhas. Quando novas regras de busca, filtros ou
persistência forem implementadas, elas devem entrar no backlog de testes com
casos de sucesso, entradas inválidas e falhas de dependências.

## Perguntas para a apresentação

- **Por que `test_config.py` é unitário?** A unidade é o comportamento de
  conversão da configuração; o ambiente é simulado e nenhum HTTP, banco ou
  servidor é usado.
- **Por que `test_health.py` é integração?** A requisição atravessa FastAPI,
  roteador, middleware e modelo de resposta.
- **Por que não usar mock no `/health`?** O endpoint não possui dependência
  externa neste estágio; adicionar mock esconderia justamente a integração
  que queremos verificar.
- **O que acontece se falhar?** `pytest` retorna código diferente de zero; o
  comando do CI falha e o merge deve aguardar correção.
- **Como isso entra no CI?** O CI não precisa conhecer cada teste: instala o
  ambiente com `uv sync --locked` e chama `uv run pytest`. Os marcadores também
  permitem executar uma camada específica para diagnóstico.
