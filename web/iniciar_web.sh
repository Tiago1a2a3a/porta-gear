#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "========================================================"
echo "  Iniciando Painel Web de Comando - Porta GEAR"
echo "  Tema: GEAR / VerLab (UFMG)"
echo "========================================================"
python3 server.py --porta 80
