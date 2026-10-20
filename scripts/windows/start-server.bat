@echo off
title Court Replay - Painel
cd /d "%~dp0..\.."
if not exist logs mkdir logs
:loop
echo [%date% %time%] iniciando painel >> logs\launcher.log
node server\src\index.js
echo [%date% %time%] painel encerrou, reiniciando em 5s >> logs\launcher.log
timeout /t 5 /nobreak >nul
goto loop
