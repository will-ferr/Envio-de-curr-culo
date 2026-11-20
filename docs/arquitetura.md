# Arquitetura

```
 Navegador ──► web (Nginx: SPA Vue + proxy /api) ──► api (FastAPI) ──► PostgreSQL
                                                         │                 ▲
                                                         └─ enfileira ──► tasks ◄── worker
                                                                                     ├─ IA (Anthropic, chave da pessoa)
                                                                                     ├─ PDF (Chromium/Playwright)
                                                                                     ├─ SMTP · IMAP · RSS
                                                                                     └─ Telegram (long polling)
```

## Camadas do back-end

| Pasta | Responsabilidade |
|---|---|
| `app/domain` | Regras puras, sem banco nem HTTP: comparação vaga × perfil, validação anti-alucinação, montagem dos documentos |
| `app/schemas` | Perfil (fonte da verdade) e formatos exigidos da IA |
| `app/ai` | Interface `AIProvider`, implementação Anthropic e provedor falso para testes |
| `app/services` | Casos de uso e integrações (vagas, documentos, funil, e-mail, Telegram, fila) |
| `app/api` | Rotas HTTP: só traduzem HTTP ↔ serviços |
| `app/worker` | Consumo da fila, agendamento e bot do Telegram |

## Decisões

### Self-hosted, uma instância por pessoa
Não há multiusuário: cada pessoa roda a própria instância. Dados pessoais de terceiros nunca ficam com o mantenedor
do projeto, e não existe custo de IA centralizado. A conta do dono existe só para proteger a interface.

### Perfil como documento JSON validado
O perfil é sempre lido e salvo por inteiro, e nenhuma consulta precisa filtrar dentro dele. Guardá-lo como JSON
(validado por Pydantic) evita 7 tabelas sem ganho real. Vagas, documentos e candidaturas — que são filtrados e
relacionados — são tabelas normais, com `CHECK` de status e índices.

### Validação anti-alucinação em duas severidades
A IA só pode **escolher e reordenar** competências, itens de experiência e projetos existentes (validados por
igualdade normalizada) — qualquer desvio é *erro* e bloqueia a aprovação. Em texto livre (título, resumo, carta),
termos com cara de tecnologia/nome próprio e "N anos" que não aparecem no perfil viram *aviso*: a heurística
pode errar, então a decisão final é da pessoa. O editor da interface segue a mesma regra: só oferece itens do perfil.

### Fila no PostgreSQL em vez de Redis
`SELECT ... FOR UPDATE SKIP LOCKED` permite vários workers sem disputa (há teste de concorrência real). Um serviço
a menos para quem instala. Tarefas têm tentativas com backoff exponencial, e as que ficam presas em `running`
(worker morto) voltam à fila.

### IA opcional e plugável
Sem chave, a análise usa palavras-chave (com sinônimos e sem contagem dupla de variantes como `node`/`node.js`) e o
currículo é montado a partir do perfil-alvo. Com chave, a saída é estruturada e validada por Pydantic. O fallback
de recusa do servidor fica ativo nos modelos que o suportam, e erros do SDK viram mensagens claras (chave inválida,
limite de uso, serviço instável — os dois últimos com nova tentativa automática).

### Telegram por long polling
A instância roda em casa, sem IP público: webhook não funcionaria. O pareamento usa um código de uso único, e só o
chat pareado consegue acionar os botões.

### PDFs com Chromium
HTML + CSS dá controle total do layout e os templates são simples de criar. O Chromium roda com JavaScript desligado
e modo offline, e o Jinja usa autoescape — o conteúdo vindo da IA não consegue injetar HTML nem carregar recursos.

## Fluxo de uma vaga

1. `POST /api/jobs` (link ou texto) → busca a página (JSON-LD `JobPosting` quando existe) → deduplica pela URL
   normalizada → enfileira `analyze_job`.
2. Worker: análise por palavras-chave; com IA, refina nota, requisitos e perfil-alvo. Se a nota passar do mínimo,
   notifica no Telegram.
3. `generate_documents`: currículo + carta → validação → PDFs.
4. Aprovação (painel ou Telegram) → envio por SMTP (com limite diário) ou "candidatei-me pelo site".
5. Funil com histórico imutável de cada transição (`application_events`).
