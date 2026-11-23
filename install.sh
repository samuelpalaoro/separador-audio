#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação Automática — Moises AI Separador de Áudio
# Compatível com Ubuntu / Debian
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo "    Instalação do Separador de Áudio por IA (Estilo Moises AI)   "
echo "=================================================================="

# 1. Identificar versão do Python adequada (Python 3.10 a 3.12 preferencial)
PYTHON_BIN=""
for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON_BIN="$py"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[-] Erro: Python 3 não encontrado no sistema."
    echo "    Instale o Python 3: sudo apt install python3 python3-venv"
    exit 1
fi

echo "[+] Utilizando interpretador: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "[+] Criando ambiente virtual em ./venv..."
    $PYTHON_BIN -m venv venv
else
    echo "[*] Ambiente virtual ./venv já existe."
fi

# 3. Atualizar pip, setuptools e wheel
echo "[+] Atualizando pip, setuptools e wheel..."
./venv/bin/pip install --upgrade pip setuptools wheel

# 4. Instalar dependências Python
echo "[+] Instalando dependências (PyTorch, Demucs, PySide6, SoundFile, SoundDevice)..."
./venv/bin/pip install -r requirements.txt

# 5. Garantir disponibilidade da biblioteca PortAudio (necessária para reprodução de áudio)
echo "[+] Verificando biblioteca de áudio PortAudio..."
if [ ! -f "lib/usr/lib/x86_64-linux-gnu/libportaudio.so.2" ]; then
    if sudo -n true 2>/dev/null; then
        echo "[+] Instalando libportaudio2 via apt..."
        sudo apt-get update && sudo apt-get install -y libportaudio2
    else
        echo "[*] Configurando PortAudio localmente em ./lib (sem necessidade de sudo)..."
        mkdir -p lib
        apt-get download libportaudio2 2>/dev/null || true
        if ls libportaudio2*.deb 1>/dev/null 2>&1; then
            dpkg -x libportaudio2*.deb ./lib/
            rm -f libportaudio2*.deb
        fi
    fi
fi

# 6. Permissões de execução
chmod +x run.sh main.py

echo ""
echo "=================================================================="
echo "  [✓] Instalação concluída com sucesso!"
echo "  Para iniciar o programa, execute:"
echo "      ./run.sh"
echo "=================================================================="
