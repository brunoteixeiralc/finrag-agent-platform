# ADR-002 - Geração com Gemini 3.7 Flash

- **Status:** aceito
- **Data:** 2026-08-14
- **Escopo:** primeiro MVP do FinRAG Agent Platform

## Contexto

Após recuperar os chunks relevantes, o FinRAG precisa gerar uma resposta curta, fundamentada e compatível com o contrato da API. O modelo deve lidar bem com português, números, citações, ambiguidade e abstention, sem ferramentas ou acesso externo.

Foram comparados `gemini-3.7-flash` e `gemini-3.6-flash`. Na tabela vigente em 14 de agosto de 2026, ambos possuem o mesmo preço unitário promocional. O custo total de cada consulta ainda depende do número efetivo de tokens de entrada, raciocínio e saída.

## Decisão

Usar:

```text
provider: google
model: gemini-3.7-flash
thinking_level: low
max_output_tokens: 800
structured_output: enabled
tools: disabled
search_grounding: disabled
```

O identificador estável `gemini-3.7-flash` será usado diretamente. O alias mutável `gemini-flash-latest` não será utilizado.

Referências oficiais:

- <https://ai.google.dev/gemini-api/docs/latest-model>
- <https://ai.google.dev/gemini-api/docs/pricing>

## Justificativa

- O modelo é estável e está disponível para produção.
- Oferece melhor capacidade atual pelo mesmo preço unitário do 3.6 durante a tabela promocional vigente.
- Suporta saída estruturada, útil para validar `status`, `answer` e referências internas.
- `thinking_level: low` é adequado a respostas RAG rápidas e reduz raciocínio desnecessário.
- O limite de 800 tokens evita respostas excessivas e ajuda a controlar custo e latência.
- Manter geração e embeddings no Google reduz integrações, credenciais e pontos de falha.

## Observação de custo

Na tabela consultada em 14 de agosto de 2026, tanto o 3.7 Flash quanto o 3.6 Flash usam preço promocional de US$ 0,75 por milhão de tokens de entrada e US$ 3,75 por milhão de tokens de saída até 31 de dezembro de 2026. A documentação informa preço padrão posterior de US$ 1,50 por milhão de tokens de entrada e US$ 7,50 por milhão de tokens de saída.

Esses valores são um snapshot e devem ser verificados novamente antes do deploy. Mesmo com preço unitário igual, dois modelos podem gerar quantidades diferentes de tokens.

## Invariantes de implementação

1. O cliente da API FinRAG não pode escolher o modelo de geração.
2. Ferramentas, busca web, URL context e grounding externo permanecem desabilitados.
3. A resposta deve ser validada contra um schema estruturado antes de ser devolvida.
4. O modelo recebe somente a pergunta, instruções do sistema e chunks recuperados.
5. Documentos são tratados como dados não confiáveis e não podem alterar instruções do sistema.
6. `temperature`, `top_p` e `top_k` de geração não serão configurados.
7. O `top_k` da API FinRAG continua sendo exclusivamente o número de chunks recuperados.
8. Respostas inválidas ou fora do schema devem falhar de forma observável; não serão silenciosamente aceitas.

## Alternativa futura

Se os golden datasets mostrarem que o 3.7 Flash é desnecessário para o nível de qualidade desejado, um modelo Flash-Lite poderá ser avaliado como otimização de custo. A troca só ocorrerá após comparar correção, fundamentação, latência e consumo de tokens.
