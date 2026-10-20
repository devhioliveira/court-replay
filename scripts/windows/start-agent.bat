@echo off
title Court Replay - Agente
cd /d "%~dp0..\.."
if not exist logs mkdir logs
:loop
echo [%date% %time%] iniciando agente >> logs\launcher.log
venv\Scripts\python.exe -m agent
echo [%date% %time%] agente encerrou, reiniciando em 5s >> logs\launcher.log
timeout /t 5 /nobreak >nul
goto loop
