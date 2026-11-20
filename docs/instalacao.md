# Guia de instalação e configuração

## 1. Instalar e abrir

1. Instale o **Docker Desktop** e abra-o (ele precisa estar rodando).
2. Baixe o projeto e crie o arquivo de configuração:

   ```bash
   git clone https://github.com/will-ferr/Envio-de-curr-culo.git candidaturas
   cd candidaturas
   cp .env.example .env
   ```

3. Edite o `.env` e troque os dois valores de exemplo. Para gerar valores aleatórios:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"      # SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(18))"  # POSTGRES_PASSWORD
   ```

   > Guarde o `SECRET_KEY`. Ele também criptografa sua chave de IA e senhas de e-mail: se ele mudar, você
   > precisará cadastrá-las de novo.

4. Suba tudo:

   ```bash
   docker compose up -d --build
   ```

5. Abra **http://localhost:8000** e crie sua conta. O painel mostra os próximos passos.

**Porta ocupada?** Troque `PORT` no `.env` (e `PUBLIC_URL` junto), depois `docker compose up -d`.

## 2. Chave de IA (Anthropic)

1. Crie uma conta em [console.anthropic.com](https://console.anthropic.com), adicione créditos e gere uma chave
   em **Settings → API Keys**.
2. No sistema: **Configurações → IA**, cole a chave e salve. Ela é validada na hora e guardada criptografada.
3. Escolha o modelo:
   - **Opus 5.5** — melhor qualidade (padrão);
   - **Sonnet 5.5** — mais barato, ótimo para a maioria das vagas;
   - **Haiku 5.5** — o mais econômico.

O consumo dos últimos 30 dias aparece na mesma tela. Seus dados de contato (nome, e-mail, telefone) **nunca**
são enviados à IA — só experiência, competências e o texto da vaga.

## 3. Perfil

Em **Perfil → Importar PDF**, envie seu currículo atual. A IA extrai os dados e **mostra para revisão** —
nada é salvo até você clicar em *Salvar perfil*. O PDF enviado é apagado logo após a leitura.

Revise com atenção: tudo que estiver aqui pode aparecer nos currículos gerados, e nada além disso.

Depois crie pelo menos um **perfil-alvo** (ex.: "Back-end Python") com as palavras-chave das vagas desse tipo.

## 4. Telegram (opcional, recomendado)

Receba as vagas compatíveis no celular e aprove com um toque.

1. No Telegram, procure **@BotFather**, envie `/newbot` e siga as instruções. Ele devolve um **token**.
2. Em **Configurações → Telegram**, cole o token e clique em *Conectar*.
3. Aparece um código: abra o seu bot no Telegram e envie `/start 123456` (o código mostrado).
4. Pronto. Use *Enviar teste* para conferir.

Só o chat pareado consegue usar os botões. Funciona sem domínio nem IP público (o worker consulta o Telegram).

## 5. E-mail (opcional)

Usado para enviar candidaturas quando a vaga pede currículo por e-mail, e para ler alertas de vaga.

**Gmail:** ative a verificação em duas etapas e gere uma **senha de app** em
<https://myaccount.google.com/apppasswords>. A senha normal não funciona.

Em **Configurações → E-mail**, use o atalho *Gmail* ou *Outlook* para preencher os servidores, informe usuário,
senha de app e remetente, e clique em *Testar conexão*.

O envio respeita o **limite diário** (padrão: 10, em Configurações → Geral) e só acontece para candidaturas
aprovadas.

### Alertas de vaga por e-mail (IMAP)

Ative a leitura e, de preferência, preencha **Somente do remetente** com o endereço dos alertas (por exemplo, o
remetente dos alertas de vaga do LinkedIn). O sistema lê e-mails dos últimos 3 dias **sem marcá-los como lidos**,
a IA extrai as vagas e cada uma é analisada. Exige a chave de IA.

## 6. Fontes RSS

Em **Configurações → Fontes de vagas**, cadastre feeds RSS de sites de vagas. Eles são verificados a cada
`SOURCES_INTERVAL_MINUTES` (padrão: 60). Use *Verificar agora* para testar.

## 7. Usar no celular pela rede de casa

Por padrão só o próprio computador acessa (`BIND_ADDRESS=127.0.0.1`). Para abrir no celular conectado ao mesmo
Wi-Fi:

1. No `.env`: `BIND_ADDRESS=0.0.0.0` e `PUBLIC_URL=http://IP-DO-COMPUTADOR:8000`.
2. `docker compose up -d`.

Não exponha a porta para a internet sem HTTPS (use um túnel como Tailscale ou Cloudflare Tunnel).

## 8. Backup, atualização e remoção

```bash
# backup do banco
docker compose exec db pg_dump -U candidaturas candidaturas > backup.sql

# atualizar para a versão mais nova
git pull && docker compose up -d --build     # as migrations rodam sozinhas

# logs (se algo der errado)
docker compose logs -f api worker

# parar / remover tudo (inclusive os dados)
docker compose down        # para
docker compose down -v     # apaga também banco e documentos
```

Em **Configurações → Geral e dados** você também pode exportar tudo em JSON ou apagar todos os dados.

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| "Chave de API inválida" | Chave copiada incompleta ou revogada; gere outra no Console. |
| Tarefas não andam ("Analisando…" para sempre) | Worker parado: `docker compose logs worker`. |
| E-mail recusado pelo Gmail | Use senha de app, não a senha da conta. |
| Link da vaga não funciona | Site exige login ou bloqueia robôs: cole o texto da vaga. |
| PDF não gera | Pouca memória compartilhada: mantenha `shm_size` do worker no compose. |
