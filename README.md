# 🏐 Court Replay

Aperte um botão na quadra e os **30 segundos** ao redor do momento viram um clip de vídeo. Os alunos acessam um **painel público** para rever, assistir e baixar as próprias jogadas.

## Sumário

- [Como funciona](#como-funciona)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Início rápido (sem câmera)](#início-rápido-sem-câmera)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso no dia a dia](#uso-no-dia-a-dia)
- [Painel público e manutenção](#painel-público-e-manutenção)
- [Segurança](#segurança)
- [Solução de problemas](#solução-de-problemas)
- [Comandos úteis](#comandos-úteis)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Desenvolvimento e testes](#desenvolvimento-e-testes)
- [Licença](#licença)

---

## Como funciona

1. A câmera filma a quadra o tempo todo (o agente mantém um buffer de segmentos curtos).
2. Alguém aperta o **botão do meio do mouse** conectado ao notebook.
3. O sistema junta **15 s antes** e **15 s depois** do clique em um único `.mp4` (sem re-encodar).
4. Em cerca de 15 segundos o clip aparece no painel web.
5. O aluno **assiste ou baixa** o vídeo.

> ⚠️ Os clips são apagados automaticamente todo dia às **00:00** (fuso `America/Sao_Paulo`). Baixe o que precisar antes disso.

---

## Arquitetura

```
┌─────────────────────┐   HTTP + HMAC   ┌─────────────────────┐
│ NOTEBOOK (quadra)   │◄───────────────►│ SERVIDOR (VPS/PC)   │
│ Agente Python       │  porta 8765     │ Painel web (Node)   │
│ FFmpeg + clips      │                 │ porta 3000          │
└──────────┬──────────┘                 └──────────┬──────────┘
           │ RTSP                                  │ HTTP
        CÂMERA                                 NAVEGADOR
```

| Componente | Onde roda | Responsabilidade |
|---|---|---|
| **Agente** (`agent/`, Python) | Notebook na quadra | Captura o RTSP com FFmpeg, detecta o botão do mouse, gera e guarda os clips, faz a limpeza diária e expõe uma API interna |
| **Servidor** (`server/`, Node.js/Express) | VPS ou PC | Serve o painel, aplica rate limit e repassa as requisições ao agente |

O navegador conversa **somente com o servidor**. Os vídeos ficam guardados **no notebook**; o servidor os repassa sob demanda. A comunicação servidor → agente é autenticada por **HMAC-SHA256** (assinatura, timestamp e nonce) usando o `NOTEBOOK_SHARED_SECRET`.

---

## Requisitos

| Onde | O que precisa |
|---|---|
| **Notebook** | Linux (Debian/Ubuntu), Python 3.10+, FFmpeg 5+ |
| **Servidor** | Node.js 20+ |
| **Rede** | O notebook alcança a câmera e o servidor alcança o notebook |

> O agente também possui um handler de mouse para Windows, mas o fluxo de instalação documentado aqui (serviço systemd) é para Linux.

---

## Início rápido (sem câmera)

Testa todo o fluxo em uma única máquina, com um vídeo sintético no lugar da câmera.

```bash
# Terminal 1 — agente em modo simulação
pip install -r requirements.txt
python -m agent --simulate

# Terminal 2 — servidor
npm install
node server/src/index.js
```

Abra `http://localhost:3000`.

---

## Instalação

### 1. Notebook (agente)

```bash
sudo apt install -y python3 python3-venv ffmpeg
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp example-config.json config.json
cp .env.example .env
```

Edite o `.env`:

```env
CAMERA_RTSP_URL=rtsp://usuario:senha@IP_DA_CAMERA:8554/profile0
NOTEBOOK_SHARED_SECRET=<senha longa e aleatória>
```

Gere uma senha forte com `openssl rand -hex 32`.

Para iniciar manualmente:

```bash
./venv/bin/python -m agent
```

Para iniciar junto com o notebook (serviço systemd):

```bash
sudo ./scripts/install.sh
```

O script instala o agente em `/opt/court-replay`, lê as variáveis de `/etc/court-replay/env` e usa o `config.json` de `/opt/court-replay`. Depois edite esses dois arquivos e inicie o serviço:

```bash
sudo systemctl start court-replay-agent
```

### 2. Servidor (painel)

```bash
npm install
cp .env.example .env
```

Edite o `.env`:

```env
NOTEBOOK_HOST=IP_DO_NOTEBOOK
NOTEBOOK_SHARED_SECRET=<a mesma senha do notebook>
APP_SECRET=<outra senha longa e aleatória>
```

> ⚠️ O `NOTEBOOK_SHARED_SECRET` precisa ser **idêntico** nas duas máquinas.

Para iniciar:

```bash
node server/src/index.js      # ou: npm start
```

Para manter ligado em produção, use o PM2:

```bash
sudo npm install -g pm2
pm2 start server/src/index.js --name court-replay
pm2 save && pm2 startup
```

Se houver um proxy reverso (nginx/traefik) na frente, ligue `TRUST_PROXY=true`; se servir por HTTPS, ligue `COOKIE_SECURE=true`.

---

## Configuração

A configuração vem de duas fontes: o **`.env`** (segredos e endereços) e o **`config.json`** (comportamento). Variáveis de ambiente têm prioridade sobre o `config.json`. O modelo completo está em [`example-config.json`](example-config.json).

### Variáveis de ambiente (`.env`)

| Variável | Usada por | Padrão | Descrição |
|---|---|---|---|
| `CAMERA_RTSP_URL` | Agente | — | URL RTSP completa da câmera |
| `CAMERA_USER` / `CAMERA_PASSWORD` | Agente | — | Credenciais da câmera (usadas se a URL RTSP não for informada) |
| `NOTEBOOK_SHARED_SECRET` | Ambos | — | Segredo HMAC; deve ser igual no notebook e no servidor |
| `APP_SECRET` | Servidor | — | Segredo das sessões |
| `NODE_HOST` / `NODE_PORT` | Servidor | `0.0.0.0` / `3000` | Endereço do painel |
| `NOTEBOOK_HOST` / `NOTEBOOK_PORT` | Servidor | `127.0.0.1` / `8765` | Onde o servidor encontra o agente |
| `AGENT_HOST` / `AGENT_PORT` | Agente | `127.0.0.1` / `8765` | Onde o agente escuta |
| `AGENT_SIMULATE` | Agente | `false` | `true` gera vídeo sintético, sem câmera |
| `DISABLE_PANEL` | Servidor | `false` | `true` tira o painel do ar (ver [manutenção](#painel-público-e-manutenção)) |
| `AUTH_ENABLED` | Servidor | `false` | Exige login para acessar o painel |
| `TRUST_PROXY` | Servidor | `false` | Ligue só atrás de proxy reverso confiável |
| `COOKIE_SECURE` | Servidor | `false` | Ligue ao servir por HTTPS |
| `TZ` | Ambos | `America/Sao_Paulo` | Fuso horário (inclusive da limpeza diária) |

### Opções principais (`config.json`)

| Opção | Padrão | O que faz |
|---|---|---|
| `buffer.preEventSeconds` | 15 | Segundos gravados antes do clique |
| `buffer.postEventSeconds` | 15 | Segundos gravados depois do clique |
| `buffer.segmentSeconds` | 2 | Duração de cada segmento do buffer |
| `buffer.maxBufferSegments` | 60 | Quantos segmentos o buffer mantém |
| `storage.maxStorageGB` | 50 | Limite de armazenamento usado como referência no status |
| `cleanup.hour` / `cleanup.minute` | 0 / 0 | Horário da limpeza diária |
| `panel.disabled` | `false` | Equivale a `DISABLE_PANEL=true` |
| `rateLimit.*` | — | Limites de requisições (global, login, trigger, download) |

---

## Uso no dia a dia

1. Abra o painel: `http://IP_DO_SERVIDOR:3000`.
2. Aperte o **botão do meio do mouse** quando quiser gravar um replay.
3. Espere uns **15 segundos** e clique em **Atualizar**.
4. O clip aparece na lista. Clique em **Visualizar** ou **Baixar**.

Dá para filtrar por horário com os campos **De / Até** e o botão **Pesquisar**.

---

## Painel público e manutenção

O painel é **aberto para os alunos**: qualquer pessoa com o link visualiza e baixa os clips do dia. **Não existe botão de excluir** — os clips somem sozinhos às 00:00.

Para tirar o painel do ar (manutenção, ou equipamento fora do lugar), ligue a flag no `.env` do servidor e reinicie:

```env
DISABLE_PANEL=true
```

```bash
pm2 restart court-replay
```

Todo acesso passa a mostrar **"Site temporariamente indisponível"**. A gravação na quadra **continua funcionando**. Para reabrir, volte para `false` e reinicie.

---

## Segurança

- Use senhas longas e aleatórias em `NOTEBOOK_SHARED_SECRET` e `APP_SECRET`.
- **Nunca** deixe a porta `8765` do notebook aberta para a internet; ela deve ser alcançável apenas pelo servidor.
- **Nunca** envie `.env` e `config.json` para o Git (já estão no `.gitignore`).
- Requisições ao agente expiram (tolerância de 5 min) e são assinadas por HMAC, o que impede replay e adulteração.
- O servidor aplica `helmet`, CORS restritivo, proteção contra HTTP parameter pollution e rate limit.

---

## Solução de problemas

| Problema | O que fazer |
|---|---|
| Painel mostra "Notebook Offline" | Confira se o agente está rodando, se o `NOTEBOOK_HOST` está certo e se o `NOTEBOOK_SHARED_SECRET` é igual nas duas máquinas |
| Câmera não conecta | Teste com `ping IP_DA_CAMERA` e confira usuário, senha e a URL RTSP |
| Clip não aparece | Aguarde ~15 segundos e clique em **Atualizar** |
| Botão do meio não funciona (Linux) | Qualquer mouse com botão do meio é aceito (só esse botão dispara). Confira se o serviço tem acesso aos dispositivos: `sudo usermod -aG input courtreplay` e reinicie. Veja no log a linha "Listening to input device" |
| FFmpeg não encontrado | `sudo apt install -y ffmpeg` |

Logs do agente:

```bash
sudo journalctl -u court-replay-agent -f
```

---

## Comandos úteis

**Notebook (agente)**

```bash
sudo systemctl start court-replay-agent
sudo systemctl stop court-replay-agent
sudo systemctl restart court-replay-agent
```

**Servidor (painel)**

```bash
pm2 restart court-replay
pm2 logs court-replay
```

---

## Estrutura do projeto

```
court-replay/
├── agent/                  # Agente Python (notebook)
│   ├── __main__.py         #   ponto de entrada (python -m agent)
│   ├── config.py           #   config.json + variáveis de ambiente
│   ├── api/                #   API interna com autenticação HMAC
│   ├── ffmpeg/             #   captura RTSP em segmentos
│   ├── input/              #   botão do meio do mouse (Linux, Windows, simulação)
│   ├── clip_manager/       #   monta o clip a partir do buffer
│   ├── storage/            #   buffer, clips e metadados
│   └── cleanup/            #   limpeza diária
├── server/                 # Painel web (Node.js/Express)
│   ├── src/                #   config, middlewares, rotas e cliente do agente
│   ├── views/              #   páginas HTML (painel, login, manutenção)
│   └── public/             #   CSS e JS do painel
├── scripts/                # install.sh e unit do systemd
├── tests/                  # testes Jest
├── example-config.json     # modelo do config.json
├── .env.example            # modelo do .env
└── docs.md                 # guia passo a passo
```

### API do servidor

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Estado do servidor e do agente |
| GET | `/api/status` | Câmera e estado do notebook |
| GET | `/api/clips?start=&end=` | Lista clips (com filtro por horário) |
| GET | `/api/clips/:id` | Informações de um clip |
| GET | `/api/clips/:id/download` | Baixa/transmite o clip (suporta `Range`) |
| POST | `/api/clips/trigger` | Dispara a criação de um clip manualmente |

---

## Desenvolvimento e testes

```bash
npm install
npm run dev     # servidor com auto-reload
npm test        # Jest com cobertura
```

Mais detalhes de instalação e operação em **[docs.md](docs.md)**.

---

## Licença

Uso interno.
