# ADR-001 - Embeddings diretos pelo Google

- **Status:** aceito
- **Data:** 2026-08-14
- **Escopo:** primeiro MVP do FinRAG Agent Platform

## Contexto

O FinRAG precisa transformar chunks e perguntas em vetores compatíveis para busca semântica no PostgreSQL com pgvector. A decisão deve favorecer simplicidade, suporte a português, custo inicial baixo e comportamento reproduzível.

Foram consideradas duas formas de acesso: integração direta com a Gemini API e acesso a modelos por meio do OpenRouter. O OpenRouter permanece uma possibilidade futura para geração ou experimentação multiprovedor, mas não é necessário para os embeddings do primeiro MVP.

## Decisão

Usar:

```text
provider: google
model: gemini-embedding-001
dimensions: 768
document_task_type: RETRIEVAL_DOCUMENT
query_task_type: RETRIEVAL_QUERY
normalization: L2
```

No PostgreSQL, a coluna será compatível com `vector(768)`.

Os chunks serão enviados com o tipo de tarefa `RETRIEVAL_DOCUMENT`. Perguntas serão enviadas com `RETRIEVAL_QUERY`. Modelo, dimensão e tipo de tarefa fazem parte da configuração controlada da aplicação, não de parâmetros fornecidos pelo cliente da API.

Como `768` é uma dimensão reduzida em relação à saída padrão do `gemini-embedding-001`, todo vetor será normalizado manualmente para norma L2 igual a 1. A documentação atual do Google exige essa normalização para dimensões não padrão desse modelo.

## Justificativa

- Integração direta reduz dependências e credenciais no MVP.
- O modelo é adequado a conteúdo textual e multilíngue.
- O corpus atual contém texto extraído de Markdown e PDF; embeddings multimodais não são necessários.
- A dimensão 768 reduz armazenamento e custo de busca em comparação com 3072 dimensões.
- Os golden datasets permitirão medir se 768 dimensões atendem à qualidade esperada.

Documentação de referência: <https://ai.google.dev/gemini-api/docs/embeddings>

## Consequências

### Positivas

- Um único espaço vetorial conhecido e reproduzível.
- Schema do pgvector definido antes das migrações.
- Menor volume de armazenamento.
- Possibilidade de usar tipos de tarefa específicos para documentos e consultas.

### Limitações

- A aplicação passa a depender da disponibilidade da Gemini API para novas ingestões e consultas.
- Trocar o modelo ou a dimensão exige reprocessar todo o corpus.
- O free tier é aceitável apenas enquanto os documentos forem públicos ou sintéticos; a política de dados deve ser reavaliada antes de conteúdo privado.

## Invariantes de implementação

1. Todo embedding persistido deve possuir exatamente 768 valores.
2. Documento e pergunta devem usar o mesmo modelo e dimensão.
3. A aplicação deve falhar visivelmente se o provedor retornar dimensão diferente.
4. O nome do modelo e a dimensão devem ser registrados junto à versão da indexação.
5. Vetores de versões diferentes não podem ser consultados no mesmo índice.
6. Timeouts e retries devem ser limitados; indisponibilidade do Google não pode ser ocultada.
7. Todo vetor de 768 dimensões deve ser normalizado e validado antes de persistência ou busca.

## Estratégia de mudança futura

Uma futura troca de modelo deve criar uma nova versão de indexação. O processo deverá:

1. Criar armazenamento ou coluna compatível com a nova dimensão.
2. Recalcular embeddings de todos os chunks.
3. Executar os golden datasets contra o novo índice.
4. Comparar qualidade, custo e latência.
5. Promover a nova versão somente após aprovação.
6. Remover a versão anterior em operação separada e recuperável.

Não será feita migração parcial misturando vetores antigos e novos.
