# Capacidade e dimensionamento

Quanta memória o servidor precisa para cada quantidade de usuários, medido na
produção em 22/11/2026.

**Servidor medido:** 2 vCPU (AMD EPYC 9354P), 7,75 GB de RAM, acervo de
1.360.708 decisões (12 GB de banco).

**Critério de aceitação:** 1 minuto por requisição.

---

## Resumo

| RAM | Usuários sustentáveis | Requisições/s | Caso médio | Pior caso | Atende 1 min? |
|---|---:|---:|---:|---:|:---:|
| **8 GB** | 171 | 12,2 | 1,6 s | 8,0 s | Sim, 7,5× de folga |
| **6 GB** | 173 | 12,3 | 1,8 s | 8,5 s | Sim, 7,1× |
| **4 GB** | **178** | **12,8** | **1,5 s** | **7,6 s** | Sim, 7,9× |
| **2 GB** | 151 | 10,8 | 2,0 s | 8,7 s | Sim, 6,9× |
| **1 GB** | 113 | 8,1 | 2,5 s | 11,4 s | Sim, 5,3× |
| **512 MB** | 110 | 7,9 | 2,7 s | 12,0 s | Sim, 5,0× |

**Usuários sustentáveis** supõe uma busca a cada 20 segundos por pessoa, com o
servidor operando a 70% da capacidade. **Caso médio** é o tempo de resposta com
20 buscas em andamento. **Pior caso** é o p95 com 50 buscas em andamento.

### O que a tabela diz

**4 GB é o ponto ótimo.** Entrega a mesma capacidade de 8 GB pela metade do
custo. Entre 4 GB e 8 GB não há ganho mensurável.

**O corte está entre 4 GB e 2 GB.** Acima dele o banco acha em memória 97% do
que procura. Abaixo, menos da metade — e cada leitura que falha vai ao disco.

| RAM | Acertos no cache |
|---|---:|
| 6 GB | 97,7% |
| 4 GB | 96,7% |
| 2 GB | 48,9% |
| 1 GB | 42,0% |
| 512 MB | 33,4% |

**Todos os níveis atendem o critério de 1 minuto**, inclusive 512 MB. A
diferença entre eles não é atender ou não atender: é quantos usuários cabem.

---

## Como os dois testes foram feitos

Foram dois testes diferentes, que respondem perguntas diferentes. Confundir um
com o outro leva a conclusões erradas.

### Teste 1 — Carga contínua

**Pergunta:** quanto o servidor aguenta processar por segundo?

Abrimos N conexões que pedem buscas **sem parar**, por 30 segundos. Assim que
uma resposta chega, outra pergunta sai. Não há pausa nenhuma — é o servidor
sendo empurrado até o limite.

**Mede:** o teto de processamento, em requisições por segundo. É desse número
que sai a conta de quantos usuários cabem no sistema.

**Não representa** uso real: pessoa de verdade lê o resultado antes de buscar de
novo. Por isso "20 buscas simultâneas" nas tabelas **não quer dizer 20
usuários** — quer dizer 20 buscas sendo processadas naquele instante, o que
corresponde a muito mais gente usando o sistema normalmente.

Cada nível de memória: Postgres reiniciado com o limite indicado, três passadas
de aquecimento do cache, e então 30 segundos de carga em cada patamar de
simultaneidade (1, 5, 10, 15, 20, 30, 40 e 50).

### Teste 2 — Rajada

**Pergunta:** o que acontece se todo mundo clicar ao mesmo tempo?

N requisições ficam presas numa barreira e são soltas **no mesmo instante**.
Cada pessoa faz **uma** busca. O cronômetro só para quando **a última** recebe
resposta. Seis rodadas por nível, para a mediana não depender de sorte.

**Mede:** como o sistema se comporta num pico, e a partir de quantas pessoas
ele deixa de dar conta.

São dois relógios diferentes, e vale distinguir:

| Medida | O que é |
|---|---|
| **Tempo da rodada** | O relógio do grupo: começa quando todos clicam e só para quando o último é atendido. |
| **p95 do pedido** | O relógio individual. 19 de cada 20 pessoas esperaram menos que isso. |

Com uma pessoa os dois são o mesmo número. Com cem, a rodada é sempre o tempo
do mais lento do grupo.

---

## Medições completas — carga contínua

### 8 GB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 6,7 | 149 ms | 112 ms | 333 ms | 471 ms |
| 5 | 13,1 | 381 ms | 271 ms | 927 ms | 1,4 s |
| 10 | 11,8 | 844 ms | 544 ms | 2,2 s | 4,5 s |
| 15 | 11,4 | 1,3 s | 777 ms | 4,3 s | 6,8 s |
| 20 | 12,5 | 1,6 s | 941 ms | 4,7 s | 8,0 s |
| 30 | 11,8 | 2,5 s | 1,9 s | 6,1 s | 7,9 s |
| 40 | 11,9 | 3,2 s | 2,8 s | 7,3 s | 10,2 s |
| 50 | 12,6 | 3,7 s | 3,6 s | 8,0 s | 10,2 s |

### 6 GB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 7,3 | 137 ms | 110 ms | 295 ms | 325 ms |
| 5 | 14,4 | 345 ms | 261 ms | 805 ms | 998 ms |
| 10 | 14,2 | 699 ms | 485 ms | 1,8 s | 2,3 s |
| 15 | 10,0 | 1,5 s | 989 ms | 3,9 s | 5,9 s |
| 20 | 10,9 | 1,8 s | 1,2 s | 5,0 s | 8,5 s |
| 30 | 12,6 | 2,3 s | 1,6 s | 6,1 s | 8,3 s |
| 40 | 13,2 | 2,9 s | 2,5 s | 6,7 s | 9,1 s |
| 50 | 12,6 | 3,8 s | 3,5 s | 8,5 s | 12,4 s |

### 4 GB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 5,1 | 196 ms | 111 ms | 349 ms | 5,8 s |
| 5 | 13,2 | 377 ms | 274 ms | 894 ms | 1,8 s |
| 10 | 12,8 | 777 ms | 501 ms | 2,0 s | 3,3 s |
| 15 | 12,8 | 1,2 s | 758 ms | 3,2 s | 4,9 s |
| 20 | 13,4 | 1,5 s | 910 ms | 4,2 s | 5,4 s |
| 30 | 13,0 | 2,3 s | 1,7 s | 6,2 s | 7,7 s |
| 40 | 11,9 | 3,2 s | 2,7 s | 7,5 s | 10,5 s |
| 50 | 12,7 | 3,7 s | 4,0 s | 7,6 s | 9,6 s |

### 2 GB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 4,8 | 209 ms | 127 ms | 510 ms | 677 ms |
| 5 | 8,2 | 602 ms | 437 ms | 1,7 s | 2,0 s |
| 10 | 8,8 | 1,1 s | 760 ms | 3,1 s | 4,2 s |
| 15 | 9,3 | 1,6 s | 1,0 s | 4,9 s | 6,5 s |
| 20 | 10,0 | 2,0 s | 1,3 s | 6,1 s | 7,8 s |
| 30 | 10,9 | 2,7 s | 2,1 s | 6,8 s | 9,2 s |
| 40 | 11,2 | 3,4 s | 2,9 s | 8,1 s | 10,8 s |
| 50 | 11,1 | 4,2 s | 4,0 s | 8,7 s | 11,6 s |

### 1 GB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 4,4 | 227 ms | 143 ms | 597 ms | 793 ms |
| 5 | 8,2 | 604 ms | 441 ms | 1,7 s | 2,2 s |
| 10 | 8,0 | 1,2 s | 862 ms | 3,6 s | 4,7 s |
| 15 | 8,1 | 1,8 s | 1,3 s | 5,4 s | 7,1 s |
| 20 | 7,7 | 2,5 s | 1,8 s | 7,6 s | 9,4 s |
| 30 | 7,7 | 3,7 s | 2,9 s | 10,5 s | 12,6 s |
| 40 | 8,3 | 4,5 s | 3,9 s | 9,7 s | 13,1 s |
| 50 | 8,6 | 5,4 s | 5,0 s | 11,4 s | 14,8 s |

### 512 MB

| Buscas simultâneas | Req/s | Média | p50 | p95 | Máximo |
|---:|---:|---:|---:|---:|---:|
| 1 | 4,0 | 249 ms | 157 ms | 654 ms | 869 ms |
| 5 | 6,7 | 738 ms | 538 ms | 2,1 s | 2,6 s |
| 10 | 6,7 | 1,5 s | 1,0 s | 4,2 s | 5,4 s |
| 15 | 7,1 | 2,1 s | 1,5 s | 6,1 s | 7,9 s |
| 20 | 7,3 | 2,7 s | 1,9 s | 7,8 s | 9,8 s |
| 30 | 7,9 | 3,6 s | 2,9 s | 9,4 s | 12,1 s |
| 40 | 7,9 | 4,6 s | 4,1 s | 11,0 s | 14,2 s |
| 50 | 8,4 | 5,5 s | 5,2 s | 12,0 s | 15,6 s |

---

## Medições completas — rajada

As tabelas acima supõem pessoas usando o sistema normalmente, cada uma no seu
ritmo. O cenário oposto é um pico: todo mundo aperta "Pesquisar" no mesmo
instante.

Medido na configuração de produção (7,75 GB, `shared_buffers` 2 GB), seis
rodadas por nível:

| Pessoas no mesmo instante | Todos atendidos em (mediana) | Pior rodada | Falhas | Atende 1 min? |
|---:|---:|---:|---:|:---:|
| 50 | 4,2 s | **5,3 s** | 0 de 300 | Sim |
| 100 | 31,6 s | 32,7 s | 115 de 600 (19%) | No limite |
| 118 | 33,4 s | **62,6 s** | 212 de 708 (30%) | **Não** |

Com 50 pessoas o sistema atende todo mundo em pouco mais de 5 segundos, sem
perder nenhuma. Com 118, uma rodada em cada duas passa de meio minuto, a pior
passa de um minuto e três de cada dez pessoas não recebem resposta.

**O limite de pico está entre 50 e 100 pessoas simultâneas, e não é memória.**
É o número de conexões que a aplicação mantém abertas com o banco: 15 por
processo, 2 processos, 30 no total. Acima disso a requisição fica esperando uma
conexão livre e desiste.

Aumentar a memória do servidor não muda esse limite. O que muda é aumentar o
pool de conexões ou o número de processos da aplicação.

---

