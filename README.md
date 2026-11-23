# Separador de Áudio por IA — Estilo Moises AI

Um aplicativo desktop moderno, elegante e de qualidade profissional para separação de músicas em faixas individuais (**stems**) usando Inteligência Artificial de última geração (**Demucs / HTDemucs v4**). 

Desenvolvido para operar **100% localmente no Ubuntu/Linux**, sem envio de dados para servidores externos e com **foco absoluto na fidelidade e qualidade de áudio**.

---

## 🎯 Principais Funcionalidades

- **Separação de Faixas por IA**:
  - **Vocals**: Voz principal e backing vocals.
  - **Drums**: Bateria e instrumentos percussivos.
  - **Bass**: Baixo elétrico, acústico e sintetizado.
  - **Other**: Guitarras, teclados, cordas e demais instrumentos.
  - **Suporte a 6 Faixas** (*HTDemucs 6s*): Faixas dedicadas para **Guitarra** e **Piano**.
- **Interface Gráfica Moderna e Intuitiva (Moises AI Style)**:
  - Tema escuro de alto contraste com identificadores visuais coloridos para cada faixa.
  - Arraste e solte de arquivos WAV com leitura e exibição imediata de metadados técnicos.
  - Barra de progresso detalhada com indicação do estágio atual do processamento neural.
  - Botão de cancelamento gracioso a qualquer momento.
- **Mixer e Reprodução Sincronizada em Tempo Real**:
  - Sistema de áudio multi-track com sincronização precisa a nível de amostras (*sample-accurate*).
  - Controles individuais por faixa: **Play/Audicionar**, **Solo** (S), **Mute** (M) e **Volume (0% a 150%)**.
  - Timeline interativa para busca (*seeking*) e visualização de tempo decorrido / total.
  - Controle de volume master.
- **Qualidade de Áudio — Prioridade Absoluta**:
  - Sem compressão com perdas (nada de MP3).
  - Preservação da profundidade de bits original (16-bit, 24-bit PCM ou 32-bit Float).
  - Preservação do número de canais (Estéreo / Mono).
  - Sem normalização destrutiva, compressores ou limiters adicionados ao áudio exportado.
  - Reconstrução opcional por interpolação *sinc* de alta qualidade para arquivos com taxas de amostragem superiores a 44.1 kHz.
- **Exportação Flexível**:
  - Exportação individual de cada stem em WAV sem perdas.
  - Exportação em lote de todas as faixas simultaneamente para uma pasta de destino.

---

## 📁 Estrutura do Projeto

O código foi estruturado de forma modular e extensível:

```
separador_audio/
├── main.py                  # Ponto de entrada da aplicação desktop
├── install.sh               # Script de instalação automatizada para Ubuntu
├── run.sh                   # Script de execução rápida
├── requirements.txt         # Lista de dependências Python
├── README.md                # Documentação técnica e de utilização
├── lib/                     # Bibliotecas locais de áudio do sistema (PortAudio)
└── src/
    ├── audio/
    │   ├── inspector.py     # Leitura e validação técnica de arquivos WAV
    │   ├── player.py        # Mixer multi-track sincronizado em tempo real (SoundDevice)
    │   └── exporter.py      # Exportador de alta fidelidade sem perdas (SoundFile)
    ├── separator/
    │   ├── demucs_engine.py # Integração com Demucs v4 (HTDemucs, HTDemucs 6s)
    │   └── worker.py        # Worker assíncrono (QThread) com suporte a cancelamento
    ├── gui/
    │   ├── main_window.py   # Janela principal do aplicativo
    │   ├── drop_zone.py     # Área de arrastar e soltar com card de metadados
    │   ├── stem_widget.py   # Linha de controle independente de cada faixa (Solo/Mute/Vol)
    │   ├── transport.py     # Barra de transporte global e timeline
    │   └── style.py         # Tema escuro e paleta de cores estilo Moises AI
    └── utils/
        ├── system_info.py   # Detecção automática de CPU, GPU (CUDA) e memória RAM
        └── formatters.py    # Formatadores de tempo, tamanho de arquivo e áudio
```

---

## 🚀 Instalação Rápida (Ubuntu / Debian)

### 1. Pré-requisitos do Sistema
Recomenda-se o **Ubuntu 22.04 LTS, 24.04 LTS** ou mais recente com **Python 3.10+**.

### 2. Instalação Automática
Abra o terminal na pasta do projeto e execute:

```bash
chmod +x install.sh run.sh
./install.sh
```

O script `install.sh`:
1. Detecta o interpretador Python adequado.
2. Cria o ambiente virtual isolado (`./venv`).
3. Instala todas as dependências (`torch`, `demucs`, `PySide6`, `soundfile`, `sounddevice`, `numpy`).
4. Configura as bibliotecas de áudio locais necessárias.

---

## 💻 Como Utilizar

Para iniciar o programa:

```bash
./run.sh
```

Ou diretamente pelo ambiente virtual:

```bash
./venv/bin/python main.py
```

Você também pode abrir um arquivo WAV diretamente na inicialização:

```bash
./run.sh /caminho/para/sua_musica.wav
```

### Passo a Passo na Interface:
1. **Importar Áudio**: Clique em *"Selecionar Arquivo WAV"* ou arraste o arquivo `.wav` para o painel superior.
2. **Conferir Metadados**: O programa exibirá o Nome, Duração, Taxa de Amostragem, Bit Depth, Canais e Tamanho.
3. **Escolher o Modelo**:
   - `HTDemucs (Padrão)`: Separação em 4 faixas (Voz, Bateria, Baixo, Outros).
   - `HTDemucs Fine-Tuned`: 4 faixas com refinamento acústico.
   - `HTDemucs 6 Faixas`: 6 faixas (adiciona Guitarra e Piano).
4. **Processar**: Clique no botão *"Separar Áudio com IA"*.
5. **Audicionar e Mixar**:
   - Pressione **Play** na barra inferior para ouvir todas as faixas juntas.
   - Pressione **S (Solo)** em qualquer faixa para isolá-la.
   - Pressione **M (Mute)** para silenciar qualquer faixa.
   - Ajuste o slider de volume de cada instrumento.
   - Clique e arraste na timeline para navegar por qualquer trecho da música.
6. **Exportar**:
   - Clique em *"Exportar WAV"* na linha de uma faixa específica.
   - Ou clique em *"💾 Exportar Todas as Faixas (WAV)"* para salvar todos os stems de uma vez.

---

## 🔬 Considerações Técnicas sobre Qualidade de Áudio

- **Arquitetura Demucs**: Os modelos HTDemucs operam internamente a `44.1 kHz, Float32, Estéreo`.
- **Preservação de Resolução**:
  - Se o seu arquivo original possuir resolução de 24-bit ou 32-bit float, as faixas exportadas mantêm o formato de 24-bit ou 32-bit float correspondente.
  - Para arquivos com taxa de amostragem diferente (por exemplo, 48 kHz ou 96 kHz), a opção ativada por padrão *"Preservar Sample Rate original ao exportar"* aplica uma interpolação *sinc* de alta fidelidade via `torchaudio.transforms.Resample`, evitando perdas ou distorções de fase.
  - O áudio exportado **não sofre nenhuma normalização arbitrária**, compressão dinâmica ou aplicação de limiters que possam alterar a dinâmica original.

---

## ⚙️ Aceleração por Hardware

- **GPU NVIDIA**: Se uma GPU NVIDIA com suporte a CUDA estiver presente, o PyTorch a utilizará automaticamente para máxima velocidade.
- **CPU**: Se não houver GPU dedicada, o programa executará perfeitamente na CPU utilizando processamento multi-core.
- **Download dos Modelos**: Na primeira vez que um modelo for utilizado, o Demucs fará o download automático do modelo pré-treinado dos servidores oficiais da Meta Research e armazenará em cache local (`~/.cache/torch/hub/checkpoints/`).
# separador-audio
