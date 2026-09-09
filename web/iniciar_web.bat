@echo off
title Porta GEAR - Servidor Web
echo ========================================================
echo   Iniciando Painel Web de Comando - Porta GEAR
echo   Tema: GEAR / VerLab (UFMG)
echo ========================================================
cd /d "%~dp0"
timeout /t 1 /nobreak >nul
start http://localhost:8088
python server.py --porta 8088
pause
