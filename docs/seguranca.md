# Segurança e privacidade

## Dados pessoais

- Tudo fica na sua máquina (volumes Docker `pgdata` e `appdata`).
- **À IA vão só:** experiências, competências, projetos, formação e o texto da vaga. **Nunca** nome, e-mail,
  telefone ou links de contato.
- O PDF enviado na importação é apagado assim que é lido. A extração vem para revisão e só é salva quando você confirma.
- Exportação completa em JSON e "apagar todos os dados" em Configurações → Geral e dados.

## Segredos

- Chave de IA, token do bot e senhas de e-mail são criptografados no banco (Fernet, chave derivada do `SECRET_KEY`
  com separação de domínio) e **nunca** voltam para o navegador — a API só informa se estão configurados.
- Campos sensíveis são mascarados nos logs.

## Acesso à interface

- Conta única do dono, criada no primeiro acesso; depois disso a rota de criação é bloqueada.
- Senha com Argon2. Sessão em cookie `HttpOnly` + `SameSite=Strict` (`Secure` quando `PUBLIC_URL` é https).
- Trocar a senha invalida todas as outras sessões.
- Proteção CSRF: toda escrita na API exige o cabeçalho `X-Requested-With`, que outro site não consegue enviar.
- Login: 5 tentativas erradas por minuto por IP; resposta idêntica para e-mail ou senha errados.
- Por padrão a porta só aceita conexões do próprio computador (`BIND_ADDRESS=127.0.0.1`).

## Conteúdo externo

- Links de vaga: só http/https; endereços internos (localhost, rede privada, metadados de nuvem) são bloqueados,
  inclusive em redirecionamentos — cada salto é validado antes da requisição. Limite de 3 MB e timeout.
- Documentos: Jinja com autoescape; Chromium com JavaScript desligado e offline; pré-visualização num iframe
  `sandbox` com CSP `default-src 'none'`.
- Telegram: conteúdo dinâmico escapado (um título com `&` ou `<` não quebra a mensagem); só o chat pareado aciona botões.
- IMAP: o filtro de remetente é higienizado antes de entrar no comando de busca.

## Envio em seu nome

- Nenhum envio sem aprovação explícita (painel ou botão do Telegram).
- Aprovação bloqueada se o currículo tiver informação que não está no perfil.
- Limite diário de envios configurável; a mesma vaga não entra duas vezes.

## Reportando vulnerabilidades

Abra uma issue privada (Security Advisory) no repositório, sem detalhes públicos até a correção.
