# ADR-005 - Recuperação vetorial e contexto insuficiente

- **Status:** aceito
- **Data:** 2026-08-14
- **Escopo:** primeiro MVP do FinRAG Agent Platform

## Contexto

Depois de transformar chunks e perguntas em embeddings, o sistema precisa decidir como ordenar os trechos, quantos fornecer ao modelo e quando recusar uma resposta. Uma recuperação permissiva demais aumenta respostas apoiadas em conteúdo apenas vagamente relacionado; uma recuperação restritiva demais perde evidências corretas.

O corpus inicial é pequeno. Portanto, velocidade de busca aproximada, reranking, busca híbrida e índices vetoriais especializados não são necessários para validar a qualidade do RAG.

Referências oficiais consultadas:

- Gemini Embeddings: <https://ai.google.dev/gemini-api/docs/embeddings>
- pgvector: <https://github.com/pgvector/pgvector>

## Decisão

Usar a seguinte configuração inicial:

```text
distance_metric: cosine
search_mode: exact
default_top_k: 5
minimum_top_k: 1
maximum_top_k: 10
initial_similarity_threshold: 0.60
reranker: disabled
hybrid_search: disabled
approximate_vector_index: disabled
```

O threshold `0.60` é uma hipótese inicial configurável, não uma constante universal nem uma garantia estatística. Ele deverá ser calibrado com os golden datasets sem alterar o contrato público.

## Preparação dos vetores

- Gerar chunks com `gemini-embedding-001`, `RETRIEVAL_DOCUMENT` e 768 dimensões.
- Gerar perguntas com o mesmo modelo, `RETRIEVAL_QUERY` e 768 dimensões.
- Normalizar cada vetor de 768 dimensões para norma L2 igual a 1 antes de persistir ou consultar.
- Rejeitar vetores com dimensão incorreta, valores não finitos ou norma zero.

A normalização manual é necessária porque a documentação atual do Google determina esse procedimento para saídas não padrão do `gemini-embedding-001`. A mesma transformação aplicada a documentos e perguntas mantém o pipeline reproduzível.

## Busca no pgvector

Usar o operador de distância cosseno `<=>`. A similaridade pública é calculada como:

```text
cosine_similarity = 1 - cosine_distance
```

O pgvector executa busca exata por padrão. Para o corpus pequeno do MVP, isso preserva recall e evita a configuração prematura de HNSW ou IVFFlat, que trocam parte do recall por velocidade.

Conceitualmente, a consulta deve:

1. Considerar somente chunks de documentos atualmente indexados.
2. Calcular a distância cosseno para a pergunta.
3. Descartar resultados com similaridade menor que `0.60`.
4. Ordenar por similaridade decrescente.
5. Retornar no máximo `top_k` chunks.

Empates devem ser resolvidos de forma determinística por `document_id`, depois `chunk_index` e `chunk_id`.

## Semântica de `top_k`

`top_k` é o número máximo de chunks elegíveis enviados para a etapa de geração após a aplicação do threshold. Assim, `top_k: 5` pode produzir de zero a cinco chunks.

O parâmetro não significa:

- Quantidade de partes criadas na ingestão.
- Quantidade de documentos distintos.
- Número de citações obrigatório.
- Probabilidade mínima de acerto.

O cliente pode escolher valores entre 1 e 10. O threshold não é exposto na API pública para impedir que cada requisição contorne a política de evidência do sistema.

## Decisão de resposta

### Nenhum chunk elegível

Se o corpus estiver vazio ou nenhum chunk atingir o threshold:

- Não chamar o modelo de geração.
- Retornar `200 OK` com `status: insufficient_context`.
- Retornar `citations: []`.

### Chunks elegíveis

Os chunks elegíveis são fornecidos ao modelo com identificadores e proveniência. O modelo pode produzir:

- `answered`, somente quando os trechos sustentarem a resposta.
- `clarification_needed`, quando existirem interpretações plausíveis e for necessária uma escolha do usuário.
- `insufficient_context`, quando os chunks forem relacionados ao tema, mas não sustentarem a resposta solicitada.

Recuperar um chunk acima do threshold não obriga o sistema a responder. O threshold avalia proximidade semântica, não suficiência factual.

## Citações e validação

- Toda resposta `answered` possui ao menos uma citação.
- O modelo só pode indicar `chunk_id` presente no contexto fornecido.
- A aplicação valida os identificadores e constrói os demais campos da citação a partir do banco.
- Citações inválidas nunca são retornadas ao cliente.
- A quantidade de citações não pode exceder a quantidade de chunks recuperados.
- `similarity` é arredondada para quatro casas decimais na resposta pública.
- O score nunca deve ser descrito como probabilidade de a resposta estar correta.

## Calibração com os golden datasets

Na primeira implementação, comparar pelo menos os thresholds:

```text
0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75
```

Manter `top_k = 5` durante essa comparação. Para cada pergunta, armazenar apenas métricas e identificadores necessários à avaliação, sem registrar conteúdo sensível.

Critérios iniciais:

1. Pelo menos 90% dos casos respondíveis devem recuperar uma evidência esperada no top 5.
2. Todos os casos explicitamente fora do corpus devem terminar em `insufficient_context`.
3. Casos de ambiguidade devem recuperar as alternativas necessárias para solicitar esclarecimento.
4. Toda citação retornada deve apontar para um chunk realmente usado e compatível com a afirmação.

Selecionar o maior threshold que preserve os critérios de recuperação e abstinência. Se nenhum valor satisfizer os critérios, investigar chunking, perguntas ou embeddings antes de simplesmente baixar o threshold.

## Testes necessários

1. Busca ordena resultados por similaridade decrescente.
2. Similaridade é calculada como `1 - distância cosseno`.
3. Vetores de documentos e perguntas são normalizados.
4. Vetor inválido ou com dimensão diferente de 768 falha visivelmente.
5. Resultado abaixo de `0.60` é descartado.
6. `top_k` limita o máximo após o threshold.
7. Corpus vazio não chama o modelo de geração.
8. Nenhum resultado elegível retorna `insufficient_context` sem citações.
9. Um resultado elegível ainda pode terminar em `insufficient_context` por falta de suporte factual.
10. Citação com `chunk_id` ausente do contexto é rejeitada.
11. Documento excluído nunca participa da recuperação.
12. Empates possuem ordem determinística.

## Fora do MVP

- HNSW ou IVFFlat.
- Reranker ou cross-encoder.
- Busca híbrida lexical e vetorial.
- Maximum Marginal Relevance.
- Filtros por tenant ou múltiplos corpora.
- Ajuste de threshold pelo cliente.

Essas técnicas só serão consideradas quando métricas de qualidade ou volume demonstrarem necessidade concreta.
