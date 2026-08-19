# FinRAG Agent Platform - Contrato da API M0

## 1. Objetivo e escopo

Este documento define o contrato HTTP do primeiro MVP antes da implementação. O MVP possui um único corpus, ingestão síncrona e consultas independentes. Ele não possui agente, ferramentas, histórico de conversa ou processamento em background.

Base URL local sugerida: `http://localhost:8000`.

Todos os endpoints funcionais usam o prefixo `/v1`. Mudanças incompatíveis exigem uma nova versão de API.

## 2. Convenções gerais

- Conteúdo: `application/json`, exceto upload de documentos.
- Identificadores internos: UUID gerado pela aplicação.
- Datas e horários: ISO 8601 em UTC.
- Datas sem horário: `YYYY-MM-DD`.
- Respostas JSON incluem `request_id`.
- O mesmo identificador também é devolvido no header `X-Request-ID`.
- O cliente pode enviar `X-Request-ID`; valores inválidos são substituídos.
- Documentos e perguntas são tratados como dados não confiáveis.
- URLs informadas como fonte são armazenadas, mas nunca acessadas pela aplicação.

## 3. Autenticação

Todos os endpoints sob `/v1` exigem:

```http
Authorization: Bearer <API_KEY>
```

O MVP utiliza uma única chave de API fornecida por variável de ambiente. Isso não representa um sistema completo de identidade ou autorização.

`/health` e `/ready` não exigem autenticação e não expõem detalhes internos.

## 4. Recurso Document

Representação pública de um documento:

```json
{
  "id": "6a719573-1851-4f3a-8950-e60a428ef948",
  "status": "indexed",
  "title": "Projeções para a evolução do PIB em 2026",
  "original_filename": "bcb_2026_projecoes_pib.pdf",
  "mime_type": "application/pdf",
  "sha256": "d9dadf82c320952f9651f530a24ff9c73efe0fc0d4d63d88e43170a53a73291d",
  "page_count": 2,
  "character_count": 6734,
  "chunks_count": 9,
  "source": {
    "name": "Banco Central do Brasil",
    "url": "https://www.bcb.gov.br/publicacoes/boxes-rpm?ano=2026",
    "published_at": "2026-06-25"
  },
  "metadata": {},
  "created_at": "2026-08-14T13:00:00Z"
}
```

O conteúdo integral e os embeddings não fazem parte da representação pública.

`chunks_count` informa quantos trechos foram criados durante a ingestão do documento. Ele não representa quantos trechos foram encontrados em uma consulta.

### Estado no MVP

Como a ingestão é síncrona, um documento só é retornado como `indexed`. Em caso de falha, a operação inteira é revertida e nenhum documento parcial permanece no banco.

### Política inicial de chunking

- Divisão orientada primeiro por página, título, seção e parágrafo.
- Tamanho alvo de 1.800 caracteres por chunk, aproximadamente 450 tokens.
- Tamanho máximo de 2.400 caracteres por chunk, aproximadamente 600 tokens.
- Sobreposição de até 300 caracteres, aproximadamente 75 tokens.
- Fragmentos muito pequenos devem ser unidos a um vizinho da mesma página ou seção quando isso não prejudicar a semântica.
- Chunks de PDF nunca atravessam páginas, preservando citações.
- Chunks de Markdown preservam o título da seção.
- Parágrafos são divididos por sentença somente quando excedem o máximo.
- Tabelas pequenas permanecem inteiras; tabelas grandes são divididas por linhas com repetição do cabeçalho.
- A sobreposição nunca atravessa documento, página ou seção semântica.

O limite por caracteres torna o processamento local determinístico e evita adicionar um tokenizer específico ao MVP. A contagem real de tokens informada pelo provedor pode ser armazenada como métrica da ingestão.

## 5. Endpoints de infraestrutura

### `GET /health`

Indica que o processo HTTP está ativo. Não verifica banco ou provedor de LLM.

Resposta `200 OK`:

```json
{
  "status": "ok"
}
```

### `GET /ready`

Verifica se a aplicação consegue acessar PostgreSQL e pgvector. O provedor de LLM não participa da readiness para evitar retirar a API de serviço durante uma falha transitória externa.

Resposta `200 OK`:

```json
{
  "status": "ready"
}
```

Resposta `503 Service Unavailable`:

```json
{
  "status": "not_ready"
}
```

## 6. Ingestão de documentos

### `POST /v1/documents`

Ingere, extrai, divide, gera embeddings e persiste um documento em uma única operação síncrona.

Content-Type: `multipart/form-data`.

| Campo | Tipo | Obrigatório | Regra |
|---|---|---:|---|
| `file` | arquivo | sim | `.md`, `.txt` ou `.pdf` |
| `title` | texto | não | Máximo de 200 caracteres; se ausente, derivar do documento ou nome do arquivo |
| `source_name` | texto | não | Máximo de 200 caracteres |
| `source_url` | texto | não | Apenas `http` ou `https`; armazenar sem acessar |
| `published_at` | data | não | Formato `YYYY-MM-DD` |
| `metadata` | JSON serializado | não | Objeto simples de até 4 KiB; máximo de 20 chaves |

Limites do MVP:

- Arquivo: até 5 MiB.
- PDF: até 50 páginas.
- Texto extraído: até 500 mil caracteres.
- Um documento por requisição.
- PDF sem texto selecionável é rejeitado; OCR não faz parte do MVP.
- Extensão, MIME declarado e conteúdo real devem ser compatíveis.

O campo `metadata` aceita valores primitivos e listas curtas. Não pode substituir campos reservados como `id`, `sha256`, `status`, `chunks_count` ou `created_at`. Metadados também são dados não confiáveis e não alteram a hierarquia de instruções do LLM.

Resposta `201 Created`:

```json
{
  "data": {
    "id": "6a719573-1851-4f3a-8950-e60a428ef948",
    "status": "indexed",
    "title": "Resultados do primeiro trimestre de 2026",
    "original_filename": "aurora_resultados_2026_t1.md",
    "mime_type": "text/markdown",
    "sha256": "f6b87c...",
    "page_count": null,
    "character_count": 1124,
    "chunks_count": 3,
    "source": {
      "name": "Aurora Financeira S.A.",
      "url": null,
      "published_at": "2026-05-10"
    },
    "metadata": {
      "external_id": "AUR-RESULT-2026-T1"
    },
    "created_at": "2026-08-14T13:00:00Z"
  },
  "deduplicated": false,
  "request_id": "4b987954-6230-4f67-9c10-ecce963ddba9"
}
```

### Idempotência por conteúdo

O SHA-256 é calculado sobre os bytes recebidos. Existe uma restrição única para esse hash no corpus.

Quando o mesmo arquivo é enviado novamente:

- Retornar `200 OK` com o documento existente.
- Retornar `deduplicated: true`.
- Não chamar novamente a API de embeddings.
- Não criar novos chunks.
- Manter os metadados da primeira ingestão.

Atualização de conteúdo ou metadados não faz parte do MVP. Uma nova versão é um novo documento; relações como `supersedes` ou `corrects` podem ser registradas em `metadata`.

## 7. Consulta e gerenciamento de documentos

### `GET /v1/documents`

Lista documentos sem retornar conteúdo ou embeddings.

Query parameters:

- `limit`: padrão 20, mínimo 1, máximo 100.
- `offset`: padrão 0, mínimo 0.

Resposta `200 OK`:

```json
{
  "data": [
    {
      "id": "6a719573-1851-4f3a-8950-e60a428ef948",
      "status": "indexed",
      "title": "Resultados do primeiro trimestre de 2026",
      "mime_type": "text/markdown",
      "chunks_count": 3,
      "created_at": "2026-08-14T13:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 1
  },
  "request_id": "4b987954-6230-4f67-9c10-ecce963ddba9"
}
```

### `GET /v1/documents/{document_id}`

Retorna a representação pública completa do documento.

- `200 OK`: documento encontrado.
- `404 Not Found`: identificador inexistente.

### `DELETE /v1/documents/{document_id}`

Remove o documento e todos os chunks associados em uma única transação.

- `204 No Content`: exclusão concluída.
- `404 Not Found`: documento inexistente ou já excluído.

Após `204`, o documento não pode aparecer na listagem, recuperação vetorial ou citações.

## 8. Consulta RAG

### `POST /v1/query`

Executa uma consulta independente sobre o corpus atual.

Request:

```json
{
  "question": "Qual é a projeção vigente de crescimento da receita da Aurora em 2026?",
  "top_k": 5
}
```

Regras:

- `question`: obrigatória, entre 1 e 2.000 caracteres após remoção de espaços externos.
- `top_k`: opcional, padrão 5, mínimo 1, máximo 10; representa o máximo de chunks elegíveis enviados à geração.
- Não há histórico de conversa.
- O modelo não recebe ferramentas.
- O sistema deve usar somente evidências do corpus.
- Conteúdo recuperado nunca pode substituir instruções do sistema.

### Estratégia de recuperação

- Gerar a pergunta com `gemini-embedding-001`, `RETRIEVAL_QUERY` e 768 dimensões.
- Normalizar vetores de chunks e perguntas para norma L2 igual a 1.
- Usar busca exata por distância cosseno no pgvector.
- Calcular `similarity` como `1 - cosine_distance`.
- Aplicar threshold inicial configurável de `0.60`.
- Ordenar por similaridade decrescente e retornar no máximo `top_k` chunks.
- Não usar HNSW, IVFFlat, busca híbrida ou reranker no MVP.

`top_k: 5` pode produzir de zero a cinco chunks, porque resultados abaixo do threshold são descartados. O threshold pertence à configuração da aplicação e não pode ser alterado pelo cliente.

Se o corpus estiver vazio ou nenhum chunk for elegível, a aplicação não chama o modelo de geração e retorna diretamente `insufficient_context`. Mesmo com chunks elegíveis, o modelo ainda deve recusar a resposta quando o contexto relacionado não contiver suporte factual suficiente.

### Resposta fundamentada

Resposta `200 OK`:

```json
{
  "status": "answered",
  "answer": "A projeção vigente é de crescimento entre 15% e 17% em 2026.",
  "citations": [
    {
      "document_id": "c35d6502-65f3-4b1e-ae26-b117fdf6966b",
      "chunk_id": "5bf3c915-657c-4900-96ce-773ae253d30b",
      "title": "Retificação do comunicado de projeção para 2026",
      "location": {
        "page_index": null,
        "page_label": null,
        "section": "Retificação do comunicado de projeção para 2026"
      },
      "excerpt": "Onde se lia 14% a 17%, leia-se 15% a 17%.",
      "similarity": 0.86
    }
  ],
  "request_id": "391619e0-1989-43d9-8d43-8011ee835eb9"
}
```

`similarity` representa proximidade vetorial, não probabilidade de a resposta estar correta. O valor é arredondado para quatro casas decimais na resposta pública.

### Contexto insuficiente

Contexto insuficiente é um resultado válido, não um erro HTTP.

```json
{
  "status": "insufficient_context",
  "answer": "Não encontrei informação suficiente nos documentos fornecidos.",
  "citations": [],
  "request_id": "391619e0-1989-43d9-8d43-8011ee835eb9"
}
```

### Pergunta ambígua

```json
{
  "status": "clarification_needed",
  "answer": "Você quer a projeção do PIB, do crédito nominal ou do crédito real?",
  "citations": [],
  "request_id": "391619e0-1989-43d9-8d43-8011ee835eb9"
}
```

Uma resposta ambígua pode incluir citações quando apresentar alternativas fundamentadas. O status continua sendo `clarification_needed` se uma escolha do usuário for necessária.

### Regras das citações

- Toda resposta `answered` deve possuir pelo menos uma citação.
- Citações são construídas pela aplicação a partir dos chunks usados, não inventadas pelo modelo.
- `page_index` começa em 1 e representa a página física do PDF.
- `page_label` preserva a numeração impressa, quando identificável.
- `section` é usada principalmente para Markdown e texto.
- `excerpt` deve ser curto e derivado do chunk original.
- Uma citação não pode apontar para documento excluído.
- Uma citação só pode usar um `chunk_id` presente no contexto enviado ao modelo.
- No máximo `top_k` citações são retornadas.

## 9. Modelo de erro

Todos os erros funcionais usam a mesma estrutura:

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "O tipo de arquivo não é aceito pelo MVP.",
    "details": {
      "allowed_types": ["text/markdown", "text/plain", "application/pdf"]
    }
  },
  "request_id": "16c57582-d812-4ad7-aa07-4de17ca1b96c"
}
```

| HTTP | Código | Situação |
|---:|---|---|
| 400 | `invalid_request` | Requisição malformada |
| 401 | `unauthorized` | Chave ausente ou inválida |
| 404 | `document_not_found` | Documento inexistente |
| 413 | `payload_too_large` | Arquivo ou texto excede o limite |
| 415 | `unsupported_media_type` | Formato não permitido ou incompatível |
| 422 | `no_extractable_text` | Arquivo válido, mas sem texto utilizável |
| 422 | `validation_error` | Campo fora das regras do contrato |
| 422 | `generation_blocked` | Geração recusada por política, segurança ou restrição de conteúdo |
| 429 | `rate_limited` | Limite de requisições excedido |
| 500 | `provider_configuration_error` | Chave, modelo ou configuração do provedor inválida |
| 500 | `internal_error` | Falha inesperada sem detalhes internos |
| 503 | `database_unavailable` | PostgreSQL indisponível |
| 503 | `llm_provider_unavailable` | Embeddings ou geração indisponíveis após tentativas limitadas |
| 504 | `llm_provider_timeout` | Prazo total de embeddings ou geração esgotado |

Stack traces, consultas SQL, prompts, chaves e respostas brutas do provedor nunca aparecem no erro público.

### Timeouts e retries

- Consulta RAG possui prazo total de 45 segundos.
- Ingestão síncrona possui prazo total de 120 segundos.
- Cada tentativa de embeddings possui timeout de até 20 segundos.
- Cada tentativa de geração possui timeout de até 30 segundos.
- Cada chamada externa admite no máximo três tentativas totais: uma inicial e dois retries.
- O intervalo usa backoff exponencial com full jitter, base de 1 segundo e teto de 4 segundos.
- Somente falhas transitórias geram retry: rede, timeout, `408`, `rate_limit_exceeded` e `5xx` recuperável.
- Erros de requisição, autenticação, permissão, modelo, cota diária ou bloqueio de conteúdo não geram retry automático.
- O prazo global sempre prevalece sobre o número máximo de tentativas.
- O cliente/SDK deve possuir uma única camada de retry; tentativas automáticas aninhadas são proibidas.
- Não há fallback silencioso de modelo ou provedor.

Falha externa é diferente de contexto insuficiente. A primeira produz erro HTTP; a segunda produz `200 OK` com `status: insufficient_context`.

## 10. Segurança e privacidade

### Upload

- Validar tamanho antes de processar quando possível.
- Validar extensão, MIME e assinatura/conteúdo.
- Normalizar o nome para exibição; nunca usar o nome recebido como caminho.
- Não executar macros, scripts, links ou conteúdo incorporado.
- Não buscar URLs encontradas no arquivo ou em metadados.
- Remover arquivos temporários depois da operação.

### Banco e transação

- Usar consultas parametrizadas.
- Usar credencial com privilégios mínimos.
- Persistir documento e chunks atomicamente.
- Excluir chunks por integridade referencial na mesma transação.
- Impor unicidade do SHA-256 no banco.

### LLM

- Tratar todo documento como conteúdo não confiável, independentemente da origem.
- Separar instruções do sistema, pergunta e contexto recuperado.
- Não fornecer ferramentas ao modelo neste MVP.
- Não permitir que conteúdo recuperado solicite prompt, segredos ou mudanças de política.
- Utilizar apenas conteúdo público ou sintético nesta fase.

### Logs

Registrar:

- `request_id`.
- Endpoint, status HTTP e duração.
- Identificador e hash do documento quando aplicável.
- Quantidade de chunks e resultado geral da operação.
- Tipo da falha externa, sem payload bruto.

Não registrar por padrão:

- Chave de API.
- Conteúdo integral de documentos.
- Embeddings.
- Prompt completo.
- Perguntas e respostas completas.
- Excertos contendo dados não previstos.

### Exposição pública

- TLS deve ser terminado no serviço de entrada da cloud.
- CORS permanece negado por padrão.
- Rate limiting deve ser aplicado antes de exposição pública.
- A chave deve vir de secret manager ou mecanismo equivalente da plataforma de deploy.

## 11. Relação com os golden datasets

| Requisito | Casos cobertos |
|---|---|
| Upload de Markdown e PDF | Corpus sintético e documentos BCB |
| Resposta com citação | `GD-001` a `GD-012`, `SYN-001` a `SYN-013` |
| Página física e impressa | Perguntas baseadas nos PDFs do BCB |
| Síntese entre fontes | `GD-011`, `GD-012`, `SYN-002`, `SYN-009`, `SYN-011` |
| Clarificação | `GD-013`, `GD-014`, `SYN-015` |
| Contexto insuficiente | `GD-015`, `SYN-016`, `SYN-018` |
| Versão e correção | `SYN-004` a `SYN-006`, `SYN-010`, `SYN-011` |
| Prompt injection | `SYN-014` |
| Idempotência | `SYN-017` |
| Exclusão | `SYN-018` |

## 12. Critérios de aceite da M0.5

O contrato está pronto para implementação quando:

1. Cada endpoint possui request, response e códigos de erro definidos.
2. Ingestão duplicada possui comportamento determinístico.
3. Falha durante ingestão não deixa estado parcial.
4. Ausência de contexto e ambiguidade são resultados explícitos.
5. Citações preservam documento, chunk e localização.
6. Exclusão impede recuperação posterior.
7. Segurança de upload e prompt injection está especificada.
8. Nenhum endpoint de agente ou ferramenta foi introduzido.

## 13. Decisões assumidas

- Um único corpus global no MVP.
- Ingestão síncrona.
- Formatos `.md`, `.txt` e PDF textual.
- Embeddings consumidos diretamente pela Gemini API do Google.
- Modelo de embeddings fixado em `gemini-embedding-001`.
- Vetores fixados em 768 dimensões no schema do pgvector.
- `RETRIEVAL_DOCUMENT` para chunks e `RETRIEVAL_QUERY` para perguntas.
- Vetores de 768 dimensões normalizados manualmente para norma L2 igual a 1.
- Geração consumida diretamente pela Gemini API do Google.
- Modelo de geração fixado em `gemini-3.7-flash`, sem alias `latest`.
- Geração com `thinking_level: low` e limite inicial de 800 tokens de saída.
- Saída estruturada habilitada; ferramentas e grounding externo desabilitados.
- Parâmetros de amostragem descontinuados (`temperature`, `top_p` e `top_k` de geração) não serão usados.
- Chunking orientado à estrutura, com alvo de 1.800 caracteres, máximo de 2.400 e sobreposição de até 300.
- Chunks de PDF não atravessam páginas; chunks de Markdown preservam seções.
- Autenticação por uma única chave Bearer.
- Idempotência por SHA-256 dos bytes recebidos.
- Resposta RAG sem streaming e sem histórico.
- Paginação por `limit` e `offset`.
- URLs são apenas metadados e nunca são acessadas.
- Queries não são persistidas por padrão.
- Consulta RAG limitada a 45 segundos e ingestão síncrona limitada a 120 segundos.
- Chamadas externas limitadas a três tentativas totais com backoff exponencial e jitter.
- Apenas erros transitórios são repetidos; não existe fallback silencioso de provedor.
- Recuperação exata por similaridade cosseno, sem índice vetorial aproximado.
- `top_k` padrão 5 e threshold inicial configurável de `0.60`.
- Ausência de chunks acima do threshold retorna `insufficient_context` sem chamar a geração.

## 14. Estado antes da Milestone 1

As decisões estruturais necessárias para iniciar a Milestone 1 estão fechadas. O threshold `0.60` é um baseline e deverá ser calibrado com os golden datasets durante a implementação, sem expor esse ajuste no contrato público.

Trocar o modelo de embeddings ou a dimensão depois da ingestão exige recalcular todos os vetores e reconstruir o índice. Vetores de modelos ou dimensões diferentes nunca devem ser misturados na mesma busca.
