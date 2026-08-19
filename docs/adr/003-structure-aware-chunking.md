# ADR-003 - Chunking estrutural por caracteres

- **Status:** aceito
- **Data:** 2026-08-14
- **Escopo:** primeiro MVP do FinRAG Agent Platform

## Contexto

O corpus mistura Markdown curto e PDFs com páginas, seções, tabelas, gráficos e notas. Os chunks precisam ser pequenos o bastante para recuperação precisa, mas grandes o bastante para preservar o sentido e sustentar citações verificáveis.

Os documentos sintéticos possuem aproximadamente 600 a 1.250 caracteres. Os textos extraídos dos três PDFs possuem aproximadamente 4.800, 6.400 e 14.600 caracteres. Uma regra puramente fixa cortaria títulos, frases ou tabelas em posições ruins.

## Decisão

Usar chunking orientado à estrutura com os seguintes limites:

```text
target_characters: 1800
max_characters: 2400
overlap_characters: 300
minimum_fragment_characters: 300
pdf_cross_page: false
markdown_preserve_headings: true
```

Segundo a referência do Gemini, um token corresponde aproximadamente a quatro caracteres. Assim, o alvo representa cerca de 450 tokens, o máximo cerca de 600 tokens e a sobreposição cerca de 75 tokens. Esses valores permanecem confortavelmente abaixo do limite de entrada do `gemini-embedding-001`.

Referências oficiais:

- <https://ai.google.dev/gemini-api/docs/tokens>
- <https://ai.google.dev/gemini-api/docs/models/gemini-embedding-001>

## Ordem de divisão

1. Documento.
2. Página, para PDFs.
3. Título ou seção.
4. Parágrafo.
5. Sentença, somente quando um parágrafo exceder o limite máximo.
6. Corte rígido, apenas como último recurso para conteúdo sem pontuação utilizável.

## Regras por formato

### Markdown e texto

- Preservar o título da seção no chunk.
- Não unir seções semanticamente diferentes somente para atingir o alvo.
- Unir fragmentos curtos quando pertencerem à mesma seção.
- Tratar frontmatter como metadado ou contexto de proveniência, não como instrução.

### PDF

- Nunca criar chunk atravessando duas páginas.
- Preservar `page_index` e `page_label` em todos os chunks.
- Remover cabeçalhos e rodapés repetidos quando identificados com segurança.
- Manter notas junto ao trecho correspondente quando isso for determinável.

### Tabelas

- Manter a tabela inteira quando ela couber em 2.400 caracteres.
- Se exceder o limite, dividir por linhas e repetir o cabeçalho em cada chunk.
- Não separar uma linha de seus rótulos ou unidades.
- Registrar que o chunk contém tabela para facilitar testes e citações.

## Sobreposição

A sobreposição máxima é de 300 caracteres e só ocorre entre chunks adjacentes da mesma página e seção. Ela deve preferir frases completas.

Não haverá sobreposição entre:

- Documentos diferentes.
- Páginas diferentes.
- Seções semanticamente independentes.
- Corpo do documento e referências bibliográficas.

## Metadados mínimos do chunk

Cada chunk deve preservar:

```text
id
document_id
chunk_index
content
character_count
provider_token_count
page_index
page_label
section
contains_table
embedding_model
embedding_dimensions
```

Campos de página podem ser nulos em Markdown. A contagem real de tokens, quando devolvida pelo Google, será armazenada para observabilidade, mas não será necessária para decidir os limites do chunk.

## Justificativa

- Evita adicionar uma biblioteca de tokenização ao primeiro MVP.
- Produz comportamento local determinístico e fácil de testar.
- Preserva páginas e seções para citações confiáveis.
- Deixa ampla margem para o limite de 2.048 tokens do modelo de embeddings.
- Permite calibrar tamanho e sobreposição usando os golden datasets.

## Critérios de teste

1. Nenhum chunk vazio.
2. Nenhum chunk acima de 2.400 caracteres, exceto uma linha indivisível explicitamente sinalizada como erro.
3. Nenhum chunk de PDF atravessa páginas.
4. A ordem dos chunks reconstrói o conteúdo sem perda, desconsiderando a sobreposição.
5. A sobreposição nunca excede 300 caracteres.
6. Títulos de Markdown acompanham seus respectivos chunks.
7. Cabeçalhos de tabelas são repetidos quando uma tabela é dividida.
8. Prompt injection presente em um documento permanece conteúdo comum do chunk.

## Estratégia de evolução

Os valores são baseline, não constantes universais. Depois da primeira execução dos golden datasets, poderão ser comparadas configurações como 1.200/200, 1.800/300 e 2.400/400 caracteres. Uma mudança exige redividir e reindexar o corpus, mantendo a configuração registrada na versão da indexação.
