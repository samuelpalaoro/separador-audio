"""
Benchmark Suite para o Separador de Áudio / SamukaLab.
Mede tempos de execução, consumo de memória RAM/VRAM e uso de CPU.
"""
import os
import sys
import time
import psutil
import torch
import numpy as np
import soundfile as sf

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def run_benchmark(iterations: int = 1) -> dict:
    process = psutil.Process(os.getpid())
    results = {}

    # 1. Medição do tempo de inicialização dos módulos
    t0 = time.perf_counter()
    from src.audio.inspector import inspect_audio_file
    from src.audio.ffmpeg_converter import FFmpegService
    from src.downloader.youtube_downloader import YouTubeDownloader
    from src.separator.demucs_engine import DemucsEngine
    t1 = time.perf_counter()
    results["module_import_time_s"] = round(t1 - t0, 3)

    # 2. Medição do carregamento do modelo
    engine = DemucsEngine()
    mem_before_load = process.memory_info().rss / (1024 * 1024)
    t2 = time.perf_counter()
    model = engine.load_model("htdemucs")
    t3 = time.perf_counter()
    mem_after_load = process.memory_info().rss / (1024 * 1024)
    results["model_load_time_s"] = round(t3 - t2, 3)
    results["model_ram_delta_mb"] = round(mem_after_load - mem_before_load, 1)

    # 3. Gerar áudio de teste de 3 segundos (44.1kHz estéreo 24-bit)
    test_wav = os.path.join(_root, "test_benchmark.wav")
    sr = 44100
    dur = 3.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sig = 0.4 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 880 * t)
    stereo = np.column_stack([sig, sig])
    sf.write(test_wav, stereo, sr, subtype="PCM_24", format="WAV")

    # 4. Medição de inferência de separação
    mem_before_sep = process.memory_info().rss / (1024 * 1024)
    cpu_before = process.cpu_percent(interval=None)
    t4 = time.perf_counter()
    stems, out_sr, meta = engine.separate(filepath=test_wav, model_name="htdemucs", shifts=1, overlap=0.25)
    t5 = time.perf_counter()
    mem_after_sep = process.memory_info().rss / (1024 * 1024)
    cpu_after = process.cpu_percent(interval=None)

    results["separation_time_s"] = round(t5 - t4, 3)
    results["peak_ram_mb"] = round(mem_after_sep, 1)
    results["stems_count"] = len(stems)
    results["cuda_available"] = torch.cuda.is_available()
    results["device"] = "cuda" if torch.cuda.is_available() else "cpu"

    if os.path.exists(test_wav):
        os.remove(test_wav)

    return results


if __name__ == "__main__":
    res = run_benchmark()
    print("=" * 60)
    print("   BENCHMARK DE DESEMPENHO (BASELINE)")
    print("=" * 60)
    for k, v in res.items():
        print(f"  • {k:25s}: {v}")
    print("=" * 60)
