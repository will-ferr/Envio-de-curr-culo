# Candidaturas

Assistente **self-hosted** e de código aberto para quem está procurando emprego: organiza as vagas, mostra o
quanto cada uma combina com você, gera um currículo e uma carta adaptados para cada vaga — **sem inventar nada
sobre você** — e acompanha o funil até a proposta.

Roda no seu computador com Docker. Seus dados e sua chave de IA nunca saem da sua máquina.

[![CI](https://github.com/will-ferr/Envio-de-curr-culo/actions/workflows/ci.yml/badge.svg)](https://github.com/will-ferr/Envio-de-curr-culo/actions/workflows/ci.yml)

## O que ele faz

1. **Perfil** — importe o currículo atual em PDF (a IA extrai os dados) e revise. Esse perfil é a fonte da verdade.
2. **Perfis-alvo** — diga que tipo de vaga você busca ("Back-end .NET", "Analista de Dados"…). Funciona para
   qualquer área, não só tecnologia.
3. **Vagas** — cole o link ou o texto, cadastre feeds RSS, ou deixe ele ler seus e-mails de alerta de vagas.
4. **Análise** — nota de compatibilidade, o que você atende e o que falta.
5. **Currículo e carta** — adaptados para a vaga, com pré-visualização e PDF em dois modelos compatíveis com ATS.
6. **Aprovação** — pelo painel ou por botões no Telegram. Nada é enviado sem você aprovar.
7. **Envio** — por e-mail (pela sua conta) quando a vaga pede, ou link direto para você se candidatar no site.
8. **Funil** — quadro de candidaturas, taxa de resposta e lembrete de follow-up.

### Regra de ouro: a IA não inventa

Todo documento gerado é verificado contra o seu perfil antes de poder ser aprovado:

- competência, experiência ou projeto que não existe no perfil → **bloqueia a aprovação**;
- item de experiência reescrito pela IA → **bloqueia** (ela só pode escolher e reordenar o que você escreveu);
- tecnologia ou "N anos de experiência" no texto livre que não aparecem no perfil → **aviso para você revisar**.

E não há robô preenchendo formulários no LinkedIn ou na Gupy: isso viola os termos dessas plataformas e costuma
terminar com a conta bloqueada.

## Instalação rápida

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) ou Docker Engine (Linux).

```bash
git clone https://github.com/will-ferr/Envio-de-curr-culo.git candidaturas
cd candidaturas
cp .env.example .env
# edite o .env: troque SECRET_KEY e POSTGRES_PASSWORD por valores aleatórios
docker compose up -d --build
```

Abra **http://localhost:8000**, crie sua conta e siga os "Primeiros passos" do painel.

O guia completo — chave de IA, Telegram, Gmail/Outlook, alertas por e-mail, backup, atualização e acesso pelo
celular — está em **[docs/instalacao.md](docs/instalacao.md)**.

### Quanto custa

O sistema é gratuito. A IA usa a **sua** chave da API da Anthropic (Claude) e o custo vai direto para a sua conta.
Você escolhe o modelo (Opus, Sonnet ou Haiku) e vê o consumo de tokens em Configurações → IA. Sem chave, o sistema
continua funcionando com análise por palavras-chave e currículo montado a partir do perfil-alvo.

## Para desenvolvedores

| Camada | Tecnologias |
|---|---|
| Back-end | Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Pydantic |
| IA | SDK oficial da Anthropic · saída estruturada validada por Pydantic · provedor plugável |
| Documentos | Jinja2 (autoescape) → HTML → PDF com Chromium (Playwright) |
| Worker | fila no próprio PostgreSQL (`FOR UPDATE SKIP LOCKED`) · Telegram por long polling |
| Front-end | Vue 3 · TypeScript · Vite · Tailwind CSS · Pinia |
| Infra | Docker Compose · Nginx · GitHub Actions |

```
web (Nginx + Vue) ──/api──► api (FastAPI) ──► PostgreSQL ◄── worker
                                                              · análise de vagas e documentos (IA)
                                                              · PDFs (Chromium)
                                                              · SMTP / IMAP / RSS
                                                              · bot do Telegram
```

Arquitetura e decisões: [docs/arquitetura.md](docs/arquitetura.md) · Segurança e privacidade:
[docs/seguranca.md](docs/seguranca.md)

### Rodando localmente sem Docker

```bash
# banco
docker run -d --name cand-db -e POSTGRES_USER=cand -e POSTGRES_PASSWORD=cand -e POSTGRES_DB=cand \
  -p 127.0.0.1:5437:5432 postgres:17-alpine

# back-end
cd backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]" && playwright install chromium
export SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
export DATABASE_URL=postgresql+psycopg://cand:cand@127.0.0.1:5437/cand
alembic upgrade head
uvicorn app.main:app --port 8001 --reload          # API
python -m app.worker                                # worker (outro terminal)

# front-end (proxy de /api para :8001)
cd frontend && npm install && npm run dev           # http://localhost:5173
```

### Testes

```bash
cd backend && pytest                                                     # SQLite em memória
TEST_DATABASE_URL=postgresql+psycopg://cand:cand@127.0.0.1:5437/cand pytest   # + testes de PostgreSQL
cd frontend && npm test
```

Os testes cobrem as regras que importam: validação anti-alucinação, comparação vaga × perfil (variantes, hífen,
acentos, sinônimos), fluxo completo vaga → currículo → aprovação → envio, transições do funil, limite diário de
envios, segurança (CSRF, sessão, segredos criptografados, bloqueio de URLs internas, rate limit de login),
pareamento e botões do Telegram, fila com concorrência real no PostgreSQL e importação de dados.

### Importando dados

```bash
# perfil em JSON (formato do export ou de examples/perfil-exemplo.json)
docker compose run --rm -v "$PWD/examples:/importar:ro" api python -m app.cli importar-perfil /importar/perfil-exemplo.json

# YAMLs do gerador antigo (base.yaml, stacks.yaml, frontends.yaml)
docker compose run --rm -v "$PWD/minha-pasta:/importar:ro" api python -m app.cli importar-legado /importar
```

## Licença

[MIT](LICENSE)
