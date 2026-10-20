# Court Replay — Produção no Windows

Guia para instalar o sistema **em um único PC Windows** na escola (agente + painel juntos). Os alunos acessam o painel pela rede local.

> **Por que não é um Serviço do Windows?** O botão do meio é capturado por um *hook* de mouse, que só funciona dentro da sessão do usuário logado. Por isso o sistema inicia por **Agendador de Tarefas ao fazer login**, com login automático.

---

## 1. Visão geral

```
  Câmera IP ──RTSP──► PC da quadra (Windows)  ◄── Wi-Fi/rede ── Celular do aluno
                      ├─ Agente (Python)  porta 8765 (só local)
                      └─ Painel (Node)    porta 3000 ◄── acesso dos alunos
```

---

## 2. Antes de ir à escola (em casa)

Teste tudo no seu PC. Na escola só mudam o IP da câmera e as configurações de rede.

### 2.1 Instalar os programas (no PC final)

| Programa | Como |
|---|---|
| Python 3.10+ | python.org (marque **Add python.exe to PATH**) |
| Node.js 20+ LTS | nodejs.org |
| FFmpeg | `winget install Gyan.FFmpeg` (feche e reabra o terminal) |

Confira, em um PowerShell novo:

```powershell
python --version
node --version
ffmpeg -version
```

### 2.2 Instalar o projeto

Copie a pasta para um local fixo, por exemplo `C:\court-replay` (evite Desktop/OneDrive). Dentro dela:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
npm.cmd install --omit=dev
copy .env.example .env
copy example-config.json config.json
```

### 2.3 Configurar o `.env`

Abra com `notepad .env` e ajuste:

```env
CAMERA_RTSP_URL=rtsp://USUARIO:SENHA@IP_DA_CAMERA:8554/profile0
NOTEBOOK_SHARED_SECRET=<senha longa aleatória>
APP_SECRET=<outra senha longa aleatória>
NOTEBOOK_HOST=127.0.0.1
DISABLE_PANEL=false
AGENT_SIMULATE=false
TZ=America/Sao_Paulo
```

Gere as senhas no PowerShell (rode duas vezes):

```powershell
-join ((48..57)+(97..102) | Get-Random -Count 48 | % {[char]$_})
```

> Como agente e painel estão no mesmo PC, `NOTEBOOK_HOST=127.0.0.1`. O `NOTEBOOK_SHARED_SECRET` é lido pelos dois do mesmo `.env`.

### 2.4 Testar a câmera antes de tudo

```powershell
ffplay -rtsp_transport tcp "rtsp://USUARIO:SENHA@IP_DA_CAMERA:8554/profile0"
```

Se abrir a imagem, a URL está certa. Se não abrir, tente `:554/stream1` no lugar de `:8554/profile0` (o caminho varia por marca). Consulte o manual da câmera.

### 2.5 Teste manual

Terminal 1: `venv\Scripts\python -m agent`
Terminal 2: `npm.cmd start`

Abra `http://localhost:3000`, aperte o **botão do meio** e, em ~15 s, clique em **Atualizar**. O selo no topo deve mostrar **Quadra online**.

---

## 3. Deixar o PC pronto para funcionar sozinho

### 3.1 Iniciar com o Windows

Com o teste manual funcionando, feche os dois terminais. Registre as tarefas (uma vez):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install-tasks.ps1
```

Elas iniciam ao fazer login, esperam 20 s pela rede e **reiniciam sozinhas** se o agente ou o painel caírem. Para iniciar agora, sem reiniciar:

```powershell
schtasks /Run /TN CourtReplay-Agent
schtasks /Run /TN CourtReplay-Server
```

Duas janelas pretas vão abrir. Deixe-as abertas (minimizadas). Os logs ficam em `logs\`.

### 3.2 Login automático

1. `Win + R` → `netplwiz` → Enter.
2. Desmarque **Os usuários devem digitar nome e senha** → OK → informe a senha.

Se a opção não aparecer, desative o Windows Hello na tela de Contas → Opções de entrada.

### 3.3 Nunca dormir

Configurações → Sistema → Energia: **Tela e suspensão = Nunca** (na tomada). Em notebook, em "O que fechar a tampa faz" escolha **Não fazer nada**.

### 3.4 Atualizações

Configurações → Windows Update → **Horas ativas** cobrindo o horário das aulas, para não reiniciar durante o uso.

### 3.5 Fuso horário

Configurações → Hora e idioma → Fuso: **Brasília**. O agente usa o fuso do `TZ` do `.env` (`America/Sao_Paulo`), que no Windows depende do pacote `tzdata`, instalado pelo `requirements.txt`. Se atualizou o projeto, rode de novo `venv\Scripts\pip install -r requirements.txt`.

---

## 4. Rede

### 4.1 IP fixo

O PC e a câmera precisam manter o mesmo IP sempre. O ideal é pedir à TI da escola uma **reserva de DHCP** pelo endereço MAC. Alternativa: IP fixo nas configurações do adaptador de rede.

### 4.2 Liberar a porta do painel (só a 3000)

PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "Court Replay Painel" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -Profile Private,Domain
```

> **Nunca** libere a porta `8765` (agente). Ela fica só dentro do PC.

Se o Windows perguntar sobre o perfil de rede, marque **Rede privada**.

### 4.3 Endereço para os alunos

Descubra o IP: `ipconfig` (campo IPv4). O painel fica em `http://IP_DO_PC:3000`. Dica: gere um **QR Code** desse endereço e cole na quadra.

> **Atenção:** muitas redes Wi-Fi de escola têm *isolamento de clientes*, que impede celulares de falarem com o PC. Teste no local com um celular. Se não funcionar, peça à TI para liberar, ou use uma rede dedicada.

---

## 5. Uso e operação

| Tarefa | Como |
|---|---|
| Gravar um replay | Botão do meio do mouse (conectado ao PC) |
| Ver o painel | `http://IP_DO_PC:3000` |
| Ver se está tudo certo | Selo **Quadra online** no topo do painel |
| Reiniciar o agente | `schtasks /End /TN CourtReplay-Agent` e depois `schtasks /Run /TN CourtReplay-Agent` |
| Reiniciar o painel | mesmo comando com `CourtReplay-Server` |
| Manutenção | `DISABLE_PANEL=true` no `.env` e reiniciar o painel |

**Dica:** use um mouse **dedicado** para o replay. O clique do meio continua funcionando nos outros programas (abre links em nova aba no navegador, por exemplo) e, se alguém usar o PC, vai gerar clips sem querer.

---

## 6. Checklist do dia da instalação

- [ ] Python, Node e FFmpeg instalados e funcionando
- [ ] IP da câmera confirmado e `ffplay` abre a imagem
- [ ] `.env` com URL da câmera e as duas senhas
- [ ] Teste manual: botão do meio gera clip no painel
- [ ] Tarefas registradas (`install-tasks.ps1`)
- [ ] Login automático, sem suspensão, fuso de Brasília
- [ ] IP fixo/reserva para o PC e para a câmera
- [ ] Porta 3000 liberada no firewall
- [ ] Acesso testado por um celular na rede da escola
- [ ] **Reiniciar o PC** e conferir que tudo sobe sozinho

---

## 7. Problemas comuns

| Problema | Solução |
|---|---|
| "Notebook Offline" no painel | Janela do agente fechada ou com erro; veja `logs\agent.log`. Rode `schtasks /Run /TN CourtReplay-Agent` |
| Imagem da câmera não abre | Cheque IP, usuário, senha e caminho RTSP (item 2.4); ping na câmera |
| Botão do meio não gera clip | O agente precisa estar rodando na sessão logada; confira o log por "Mouse hook installed" |
| Celular não abre o painel | Firewall (4.2), IP correto (4.3) ou isolamento do Wi-Fi |
| Horário dos clips 3h adiantado | Atualize o projeto e rode `venv\Scripts\pip install -r requirements.txt` (instala o `tzdata`). Clips antigos mantêm o horário errado até a limpeza da meia-noite |
| Nada sobe após reiniciar | Login automático (3.2) não configurado; tarefas só iniciam após login |
| `npm` bloqueado no PowerShell | Use `npm.cmd`, ou `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
