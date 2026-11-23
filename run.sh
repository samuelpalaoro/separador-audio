#!/usr/bin/env bash
# ==============================================================================
# Script de Inicialização — Moises AI Separador de Áudio
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "[-] Ambiente virtual não encontrado. Executando instalação inicial..."
    ./install.sh
fi

# Configurar caminhos de biblioteca dinâmica para PortAudio local se existir
if [ -d "$SCRIPT_DIR/lib/usr/lib/x86_64-linux-gnu" ]; then
    export LD_LIBRARY_PATH="$SCRIPT_DIR/lib/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"
fi

# Forçar tema escuro padrão para Qt se aplicável
export QT_QPA_PLATFORMTHEME=gtk3

# Iniciar programa desktop
exec "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/main.py" "$@"
