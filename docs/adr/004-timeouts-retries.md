# ADR-004 - Timeouts, retries e falhas externas

- **Status:** aceito
- **Data:** 2026-08-14
- **Escopo:** primeiro MVP do FinRAG Agent Platform

## Contexto

O MVP depende de dois sistemas externos ao processo HTTP: PostgreSQL e Gemini API. Falhas temporárias são esperadas, mas tentativas ilimitadas aumentam latência, custo e risco de operações duplicadas. Também seria incorreto esconder uma falha do provedor produzindo uma resposta sem evidência ou trocando silenciosamente de modelo.

A documentação oficial do Gemini recomenda backoff exponencial com jitter, limitado a erros transitórios e com um número máximo de tentativas. Ela também informa que os SDKs oficiais já podem executar retries automaticamente. Portanto, o MVP deve possuir uma única camada responsável por essa política, evitando retries aninhados.

Referências oficiais consultadas:

- <https://ai.google.dev/gemini-api/docs/troubleshooting>
- <https://ai.google.dev/gemini-api/docs/api-errors>

## Decisão

### Prazos máximos

| Operação | Timeout |
|---|---:|
| Conexão com Gemini API | 5 segundos |
| Uma tentativa de embeddings | 20 segundos |
| Uma tentativa de geração | 30 segundos |
| Obter conexão com PostgreSQL | 5 segundos |
| Comando comum no PostgreSQL | 10 segundos |
| Verificação do banco em `/ready` | 2 segundos |
| Operação completa de consulta RAG | 45 segundos |
| Operação completa de ingestão síncrona | 120 segundos |

Os timeouts por tentativa nunca ampliam o prazo da operação completa. Quando o tempo restante for menor, ele passa a ser o limite efetivo da próxima tentativa. O cancelamento da requisição pelo cliente cancela o trabalho ainda em andamento e não gera retry.

### Quantidade e espera entre tentativas

- No máximo três tentativas totais por chamada externa: uma inicial e até dois retries.
- Backoff exponencial com full jitter.
- Atraso-base de 1 segundo e teto de 4 segundos.
- Respeitar `Retry-After` quando fornecido, sem ultrapassar o prazo da operação.
- O mesmo limite total se aplica independentemente de a política estar no cliente HTTP, SDK ou aplicação.
- Configurar ou desabilitar os retries automáticos do SDK para impedir multiplicação de tentativas.

Exemplo de limites de espera: antes do primeiro retry, entre 0 e 1 segundo; antes do segundo, entre 0 e 2 segundos. O jitter impede várias instâncias de repetirem a chamada ao mesmo tempo.

### Falhas que podem gerar retry

- Timeout, falha de conexão ou conexão interrompida.
- HTTP `408`.
- HTTP `429` com código do provedor `rate_limit_exceeded`.
- HTTP `500`, `502`, `503` ou `504`.

### Falhas que não geram retry automático

- HTTP `400`, `401`, `403`, `404`, `413`, `415` ou `422`.
- HTTP `429` com código `quota_exceeded`, pois aguardar poucos segundos não recupera uma cota diária.
- Modelo inexistente, chave inválida, permissão ausente ou configuração inválida.
- Bloqueio de conteúdo por segurança, recitação, idioma, conteúdo proibido, dados pessoais sensíveis ou blocklist.
- Cancelamento feito pelo cliente.

Uma eventual resposta estruturada inválida do modelo pode consumir somente um dos dois retries já previstos. Ela não cria um orçamento adicional de tentativas.

## Comportamento terminal da API

| Falha final | Resposta pública | Regra |
|---|---|---|
| Gemini indisponível após os retries | `503 llm_provider_unavailable` | Não retornar resposta RAG parcial |
| Prazo total da operação esgotado | `504 llm_provider_timeout` | Não continuar em background |
| Chave, modelo ou configuração do provedor inválida | `500 provider_configuration_error` | Não expor detalhes da configuração |
| Geração bloqueada por política ou segurança | `422 generation_blocked` | Não repetir automaticamente nem expor texto bruto do provedor |
| PostgreSQL indisponível | `503 database_unavailable` | Não simular sucesso |

Não haverá fallback para outro modelo ou provedor no MVP. Uma falha deve permanecer visível, rastreável pelo `request_id` e distinta de `insufficient_context`. Este último significa que o sistema funcionou, mas o corpus não sustentou uma resposta.

## Atomicidade da ingestão

1. Validar, extrair e dividir o documento.
2. Gerar todos os embeddings necessários.
3. Somente então abrir a transação que persiste documento e chunks.
4. Confirmar tudo em um único commit.

Se qualquer embedding falhar, nenhuma linha do documento é persistida. Se uma transação falhar, ela é revertida. A aplicação não repete automaticamente uma transação cujo resultado de commit seja incerto; a restrição única de SHA-256 protege uma nova requisição explícita contra duplicação.

## Observabilidade segura

Registrar para cada chamada externa:

- `request_id`.
- Tipo da operação: embedding, geração ou banco.
- Número da tentativa e total de tentativas.
- Duração e categoria terminal da falha.
- Status HTTP ou código normalizado do provedor, quando disponível.

Não registrar chave, prompt completo, conteúdo integral, embedding ou resposta bruta do provedor.

## Critérios de teste

1. Duas falhas transitórias seguidas de sucesso resultam em três tentativas totais.
2. Erro permanente resulta em apenas uma tentativa.
3. `rate_limit_exceeded` respeita backoff e o prazo global.
4. `quota_exceeded` não gera retry curto inútil.
5. O prazo global interrompe novas tentativas mesmo que o limite de três não tenha sido atingido.
6. Retries automáticos do SDK não multiplicam a política da aplicação.
7. Falha de embeddings não deixa documento ou chunks parciais.
8. Falha de geração nunca devolve uma resposta como se estivesse fundamentada.
9. Bloqueio de segurança é diferente de contexto insuficiente.
10. Logs possuem `request_id` e contagem de tentativas, mas não possuem payload sensível.

## Consequências

- Falhas curtas podem ser recuperadas sem intervenção do cliente.
- A latência e o custo máximos ficam limitados.
- O comportamento é simples de testar com relógio e cliente simulados.
- Uma indisponibilidade prolongada permanece visível; resiliência com filas, circuit breaker ou múltiplos provedores fica fora do MVP.
