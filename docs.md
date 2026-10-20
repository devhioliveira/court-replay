# Court Replay — Guia

Guia simples para instalar e usar o sistema.

---

## 1. Usando no dia a dia

1. Abra o painel: `http://IP_DO_SERVIDOR:3000`
2. Aperte o **botão do meio do mouse** quando quiser gravar um replay.
3. Espere uns **5 segundos** e clique em **Atualizar**.
4. O clip aparece na lista. Clique em **Visualizar** ou **Baixar**.

Dá para filtrar por horário usando os campos **De / Até** e o botão **Pesquisar**.

> ⚠️ Os clips são apagados todo dia às **00:00**. Baixe o que precisar antes disso.

---

## 2. Como o sistema é dividido

| Máquina | Função |
|---|---|
| **Notebook** (na quadra) | Fica ligado na câmera, grava o vídeo e gera os clips |
| **Servidor** (VPS ou PC) | Mostra o painel web para os usuários |

O navegador só conversa com o servidor. Os vídeos ficam guardados no notebook.

---

## 3. O que você precisa

**Notebook:** Linux (Debian/Ubuntu), Python 3.10+ e FFmpeg 5+.
**Servidor:** Node.js 20+.
**Rede:** o notebook deve alcançar a câmera, e o servidor deve alcançar o notebook.

---

## 4. Instalação

### 4.1 Notebook

    sudo apt install -y python3 python3-venv ffmpeg
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    cp example-config.json config.json
    cp .env.example .env

Abra o `.env` e preencha:

    CAMERA_RTSP_URL=rtsp://usuario:senha@IP_DA_CAMERA:8554/profile0
    NOTEBOOK_SHARED_SECRET=<senha longa e aleatória>

Para gerar uma senha forte: `openssl rand -hex 32`

Para iniciar:

    ./venv/bin/python -m agent

Para iniciar sozinho com o notebook (como serviço):

    sudo ./scripts/install.sh

### 4.2 Servidor

    npm install
    cp .env.example .env

Abra o `.env` e preencha:

    NOTEBOOK_HOST=IP_DO_NOTEBOOK
    NOTEBOOK_SHARED_SECRET=<a mesma senha do notebook>
    APP_SECRET=<outra senha longa e aleatória>

Para iniciar:

    node server/src/index.js

Para manter ligado em produção, use o PM2:

    sudo npm install -g pm2
    pm2 start server/src/index.js --name court-replay
    pm2 save && pm2 startup

> ⚠️ O `NOTEBOOK_SHARED_SECRET` precisa ser **idêntico** nas duas máquinas.

### 4.3 Teste rápido (uma máquina, sem câmera)

    python -m agent --simulate                # terminal 1
    node server/src/index.js                  # terminal 2

Abra `http://localhost:3000`.

---

## 5. Configurações principais

No arquivo `config.json`:

| Opção | Padrão | O que faz |
|---|---|---|
| `buffer.preEventSeconds` | 30 | Segundos gravados antes do clique |
| `buffer.postEventSeconds` | 0 | Segundos gravados depois do clique (0 = nada depois) |
| `cleanup.hour` / `minute` | 0 / 0 | Horário da limpeza diária |
| `panel.disabled` | false | Tira o painel do ar (o mesmo que `DISABLE_PANEL=true`) |

Todas as opções estão em `example-config.json`.

---

## 6. Painel público e manutenção

O painel é **público, feito para os alunos** verem as jogadas que fizeram. Qualquer pessoa com o link pode visualizar e baixar os clips do dia. Não é possível excluir clips pelo painel, e eles somem sozinhos às 00:00.

### Tirar o painel do ar

Use a flag `DISABLE_PANEL` no `.env` do servidor:

    DISABLE_PANEL=true

Reinicie o servidor (`pm2 restart court-replay`). Todo acesso passa a mostrar o aviso **"Site temporariamente indisponível"**.

Use quando o sistema estiver em manutenção ou quando o notebook/câmera estiver fora do lugar.

- A gravação **continua funcionando**: o botão do mouse segue gerando clips no notebook.
- Para reabrir, coloque `DISABLE_PANEL=false` e reinicie o servidor.

### Cuidados básicos

- Use senhas longas e aleatórias em `NOTEBOOK_SHARED_SECRET` e `APP_SECRET`.
- Nunca deixe a porta `8765` do notebook aberta para a internet.
- Nunca envie os arquivos `.env` e `config.json` para o Git.

---

## 7. Problemas comuns

| Problema | O que fazer |
|---|---|
| Painel mostra "Notebook Offline" | Confira se o agente está rodando, se o `NOTEBOOK_HOST` está certo e se as senhas (`NOTEBOOK_SHARED_SECRET`) são iguais |
| Câmera não conecta | Teste com `ping IP_DA_CAMERA` e confira usuário, senha e a URL RTSP |
| Clip não aparece | Aguarde ~5 segundos e clique em **Atualizar** |
| Botão do meio não funciona (Linux) | Rode `sudo usermod -aG input courtreplay` e reinicie o serviço |
| FFmpeg não encontrado | `sudo apt install -y ffmpeg` |

Para ver os logs do agente:

    sudo journalctl -u court-replay-agent -f

---

## 8. Comandos úteis

**Notebook**

    sudo systemctl start court-replay-agent
    sudo systemctl stop court-replay-agent
    sudo systemctl restart court-replay-agent

**Servidor**

    pm2 restart court-replay
    pm2 logs court-replay

**Testes**

    npm test
