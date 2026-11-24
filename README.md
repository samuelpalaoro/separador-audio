# Separador de Áudio por IA — Estilo Moises AI

Um aplicativo desktop moderno, elegante e de qualidade profissional para separação de músicas em faixas individuais (**stems**) usando Inteligência Artificial de última geração (**Demucs / HTDemucs v4**), com suporte a **arquivos locais** e **links diretos do YouTube** via **yt-dlp** e **FFmpeg**.

Desenvolvido para operar **100% localmente no Ubuntu/Linux**, sem envio de dados para servidores externos e com **foco absoluto na fidelidade e integridade sonora**.

---

## 🎯 Principais Funcionalidades

- **Múltiplos Modos de Entrada**:
  - **🔗 Link do YouTube**: Cole qualquer link de vídeo, clipe ou música do YouTube (`youtube.com/watch?v=...`, `youtu.be/...`, `music.youtube.com/...`). O áudio é baixado e preparado automaticamente.
  - **📁 Arquivos Locais**: Suporte nativo a arrastar e soltar (Drag & Drop) de arquivos `.wav`, além de compatibilidade com outros formatos através de conversão automática com FFmpeg.
- **Integração Automatizada com yt-dlp**:
  - Download exclusivo do melhor fluxo de áudio da fonte (`bestaudio/best`), economizando banda e tempo sem baixar fluxos de vídeo.
  - Extração assíncrona de metadados prévios (Título do vídeo, Canal e Duração).
  - Sanitização rígida de títulos para prevenção de caracteres ilegais e injeção de comandos.
- **Preparação e Normalização com FFmpeg**:
  - Conversão inteligente e rápida para o formato ideal do modelo neural: **WAV PCM 24-bit ou 16-bit, 44.100 Hz, 2 canais (Estéreo)**.
  - Chamadas de sistema sem uso de shell (`shell=False`) para máxima segurança.
- **Separação de Faixas por IA (Demucs v4)**:
  - **Vocals**: Voz principal e backing vocals.
  - **Drums**: Bateria e instrumentos percussivos.
  - **Bass**: Baixo elétrico, acústico e sintetizado.
  - **Other**: Guitarras, teclados, sintetizadores e demais instrumentos.
  - **Suporte a 6 Faixas** (*HTDemucs 6s*): Faixas dedicadas para **Guitarra** e **Piano**.
- **Interface Gráfica Moderna e Intuitiva (Moises AI Style)**:
  - Tema escuro de alto contraste com identificadores visuais coloridos para cada faixa.
  - Indicador visual das 4 etapas do pipeline: *1. Download -> 2. FFmpeg -> 3. Demucs IA -> 4. Concluído*.
  - Acompanhamento em tempo real de velocidade de download (MB/s) e tempo restante (ETA).
  - Botão de cancelamento gracioso a qualquer momento.
  - Botão **"📁 Abrir Pasta de Resultados"** para acesso instantâneo aos arquivos gerados.
- **Organização Automática dos Resultados**:
  - Os resultados de cada música processada são salvos organizadamente no diretório `output/<Nome_da_Musica>/`:
    ```
    output/
    └── Nome_da_Musica/
        ├── original.wav
        ├── Nome_da_Musica_vocals.wav
        ├── Nome_da_Musica_drums.wav
        ├── Nome_da_Musica_bass.wav
        └── Nome_da_Musica_other.wav
    ```
- **Mixer e Reprodução Sincronizada em Tempo Real**:
  - Sistema de áudio multi-track com sincronização precisa a nível de amostras (*sample-accurate*).
  - Controles individuais por faixa: **Play/Audicionar**, **Solo** (S), **Mute** (M) e **Volume (0% a 150%)**.
  - Timeline interativa para busca (*seeking*) e visualização de tempo decorrido / total.
  - Controle de volume master.
- **Exportação Flexível**:
  - Exportação individual de cada stem em WAV sem perdas.
  - Exportação em lote de todas as faixas simultaneamente para qualquer pasta selecionada.

---

## 📁 Estrutura do Projeto

```
separador_audio/
├── main.py                          # Ponto de entrada da aplicação desktop
├── install.sh                       # Script de instalação automatizada para Ubuntu
├── run.sh                           # Script de execução rápida
├── requirements.txt                 # Dependências Python (PySide6, Demucs, Torch, yt-dlp, etc.)
├── README.md                        # Documentação técnica e de utilização
├── lib/                             # Bibliotecas locais de áudio do sistema (PortAudio)
├── output/                          # Diretório padrão de saída organizada por música
└── src/
    ├── downloader/
    │   ├── __init__.py
    │   └── youtube_downloader.py    # Integração oficial com yt-dlp e worker assíncrono de info
    ├── audio/
    │   ├── inspector.py             # Leitura e validação técnica de arquivos WAV
    │   ├── ffmpeg_converter.py      # Serviço e conversor de áudio baseado no FFmpeg
    │   ├── player.py                # Mixer multi-track sincronizado em tempo real (SoundDevice)
    │   └── exporter.py              # Exportador de alta fidelidade sem perdas (SoundFile)
    ├── separator/
    │   ├── demucs_engine.py         # Motor de separação por IA (Demucs v4)
    │   ├── pipeline_worker.py       # UnifiedPipelineWorker (QThread de Download + FFmpeg + Demucs)
    │   └── worker.py                # Worker legado mantido para retrocompatibilidade
    ├── gui/
    │   ├── main_window.py           # Janela principal com abas de YouTube e Arquivo Local
    │   ├── drop_zone.py             # Área de arrastar e soltar com card de metadados
    │   ├── stem_widget.py           # Linha de controle independente de cada faixa (Solo/Mute/Vol)
    │   ├── transport.py             # Barra de transporte global e timeline
    │   └── style.py                 # Tema escuro e paleta de cores estilo Moises AI
    └── utils/
        ├── system_info.py           # Detecção automática de CPU, GPU (CUDA) e memória RAM
        └── formatters.py            # Formatadores de tempo, tamanho de arquivo e áudio
```

---

## 🚀 Instalação e Requisitos (Ubuntu / Debian / Linux)

### 1. Pré-requisitos do Sistema
- **Sistema Operacional:** Ubuntu 20.04+, 22.04 LTS, 24.04 LTS ou qualquer distribuição Linux moderna.
- **Python:** Python 3.10 a 3.12.
- **FFmpeg:** Utilitário FFmpeg para conversão de áudio.
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

### 2. Instalação Automática
Abra o terminal na pasta do projeto e execute o script de instalação:

```bash
chmod +x install.sh run.sh
./install.sh
```

O script `install.sh`:
1. Detecta o interpretador Python adequado.
2. Cria o ambiente virtual isolado (`./venv`).
3. Instala todas as dependências (`torch`, `demucs`, `PySide6`, `yt-dlp`, `soundfile`, `sounddevice`, `numpy`).
4. Valida a presença do `ffmpeg` no sistema.
5. Configura as bibliotecas de áudio locais necessárias (`libportaudio2`).

---

## 💻 Como Utilizar

Para iniciar o programa desktop:

```bash
./run.sh
```

Ou diretamente pelo ambiente virtual:

```bash
./venv/bin/python main.py
```

### Fluxo de Uso com Link do YouTube:
1. Abra o aplicativo e selecione a aba **"🔗 Link do YouTube"**.
2. Cole a URL do vídeo no campo de texto (ou clique em **"📋 Colar"**).
3. Clique em **"🔍 Validar Link"** (ou pressione *Enter*) para conferir o título, canal e duração do vídeo.
4. Clique em **"⚡ Separar Áudio com IA"**.
5. Acompanhe as 4 etapas no painel:
   - *1. Download do fluxo de áudio* (com velocidade em MB/s e ETA).
   - *2. Preparação e conversão para WAV via FFmpeg*.
   - *3. Separação neural por IA via Demucs*.
   - *4. Organização automática dos resultados*.
6. Ao finalizar, ouça as faixas separadas no mixer da interface ou clique em **"📁 Abrir Pasta de Resultados"** para abrir o diretório com os arquivos `.wav`.

### Fluxo de Uso com Arquivo Local:
1. Selecione a aba **"📁 Arquivo Local"**.
2. Arraste e solte o arquivo `.wav` no painel central ou clique em *"Selecionar Arquivo WAV"*.
3. Clique em **"⚡ Separar Áudio com IA"**.

---

## 🧪 Bateria de Testes Automatizados

O projeto conta com suítes de testes unitários, testes de integração e testes rigorosos de estabilidade:

```bash
# Testes específicos do pipeline do YouTube e FFmpeg
./venv/bin/python -m unittest tests/test_youtube_downloader.py tests/test_ffmpeg_converter.py tests/test_pipeline_worker.py tests/test_youtube_pipeline.py

# Teste rigoroso de estabilidade e integridade
./venv/bin/python tests/test_rigorous_suite.py
```

---

## ⚙️ Aceleração por Hardware

- **GPU NVIDIA com CUDA**: Detectada e utilizada automaticamente pelo PyTorch para máxima velocidade na inferência neural.
- **CPU Multi-Core**: Caso não haja GPU dedicada, o processamento ocorre via CPU utilizando todos os núcleos disponíveis.
