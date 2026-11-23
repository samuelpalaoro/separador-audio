"""Comprehensive test for full audio separation and playback pipeline."""
import os
import sys
import numpy as np
import soundfile as sf
import torch

from src.audio.inspector import inspect_audio_file
from src.separator.demucs_engine import DemucsEngine
from src.audio.player import MultiTrackPlayer
from src.audio.exporter import export_all_stems, export_stem_to_wav

def generate_test_audio(filepath: str, duration_sec: float = 4.0, sr: int = 48000):
    """Generate a realistic musical audio WAV file with bass, kick drum, snare, melody."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # 1. Bassline (80 Hz with harmonics)
    bass = 0.3 * np.sin(2 * np.pi * 80 * t) + 0.15 * np.sin(2 * np.pi * 160 * t)
    
    # 2. Drums: Kick pulses (120 BPM = 2 Hz) + Snare noise
    kick = np.zeros_like(t)
    snare = np.zeros_like(t)
    beat_samples = int(sr * 0.5)  # 120 bpm = beat every 0.5s
    for i in range(0, len(t), beat_samples):
        # Kick on beats 0, 2, 4...
        k_len = min(int(sr * 0.15), len(t) - i)
        k_t = np.linspace(0, 0.15, k_len)
        kick[i:i + k_len] += 0.5 * np.sin(2 * np.pi * 60 * np.exp(-15 * k_t) * k_t) * np.exp(-10 * k_t)
        
        # Snare on beats 1, 3...
        if i + beat_samples // 2 < len(t):
            s_idx = i + beat_samples // 2
            s_len = min(int(sr * 0.12), len(t) - s_idx)
            snare[s_idx:s_idx + s_len] += 0.3 * (np.random.rand(s_len) * 2 - 1) * np.exp(-20 * np.linspace(0, 0.12, s_len))

    # 3. Synth / Vocals Melody (440 Hz, 554 Hz, 659 Hz arpeggio)
    melody = np.zeros_like(t)
    notes = [440.0, 554.37, 659.25, 880.0]
    note_dur = int(sr * 0.25)
    for n_idx, note_start in enumerate(range(0, len(t), note_dur)):
        freq = notes[n_idx % len(notes)]
        n_len = min(note_dur, len(t) - note_start)
        n_t = t[note_start:note_start + n_len]
        melody[note_start:note_start + n_len] = 0.25 * np.sin(2 * np.pi * freq * n_t) * (1 - np.linspace(0, 0.8, n_len))

    # Stereo mix
    left = bass + kick + snare * 0.7 + melody * 0.8
    right = bass + kick + snare * 0.7 + melody * 0.5
    stereo = np.column_stack([left, right])
    stereo = np.clip(stereo, -0.95, 0.95)

    # Write as 24-bit PCM WAV (high resolution)
    sf.write(filepath, stereo, sr, subtype="PCM_24", format="WAV")
    print(f"[+] Áudio de teste gerado em: {filepath} ({sr} Hz, 24-bit PCM, Estéreo)")


def main():
    test_wav = "test_song.wav"
    out_dir = "test_output_stems"
    
    print("--- 1. Gerando áudio de teste de alta resolução (24-bit, 48kHz) ---")
    generate_test_audio(test_wav, duration_sec=3.5, sr=48000)
    
    print("\n--- 2. Inspecionando metadados técnicos ---")
    meta = inspect_audio_file(test_wav)
    print(f"Nome: {meta['filename']}")
    print(f"Duração: {meta['duration_formatted']} ({meta['duration']:.2f}s)")
    print(f"Sample Rate: {meta['samplerate_formatted']}")
    print(f"Bit Depth: {meta['bit_depth']}")
    print(f"Canais: {meta['channels_formatted']}")
    print(f"Tamanho: {meta['filesize_formatted']}")
    
    assert meta["channels"] == 2, "Canais inválidos"
    assert meta["samplerate"] == 48000, "Sample rate inválido"
    assert "24-bit" in meta["bit_depth"], "Bit depth inválido"

    print("\n--- 3. Executando Separação por IA com Demucs (htdemucs) ---")
    engine = DemucsEngine()
    
    def on_progress(pct, msg):
        print(f"  [{pct:3d}%] {msg}")

    stems, sr, orig_meta = engine.separate(
        filepath=test_wav,
        model_name="htdemucs",
        shifts=1,
        overlap=0.25,
        progress_callback=on_progress
    )

    print(f"\n[✓] Separação concluída! Faixas geradas: {list(stems.keys())}")
    for name, data in stems.items():
        print(f"  • {name}: shape={data.shape}, dtype={data.dtype}, min={data.min():.3f}, max={data.max():.3f}")
        assert data.shape[0] > 0, f"Faixa {name} vazia!"

    print("\n--- 4. Testando MultiTrackPlayer (Mixer sincronizado) ---")
    player = MultiTrackPlayer(sample_rate=sr)
    player.load_stems(stems, sample_rate=sr)
    print(f"Duração carregada no Player: {player.duration_seconds:.2f}s")
    
    # Test solo and mute toggles
    first_stem = list(stems.keys())[0]
    player.set_stem_volume(first_stem, 0.8)
    player.set_stem_solo(first_stem, True)
    player.set_stem_muted(first_stem, False)
    player.seek(1.0)
    assert abs(player.current_time_seconds - 1.0) < 0.1, "Seek incorreto!"
    print(f"[✓] Player configurado, Solo/Mute e Seek testados com sucesso.")

    print("\n--- 5. Testando Exportação de Stems sem Perdas em WAV ---")
    exported_files = export_all_stems(
        stems=stems,
        stem_sample_rate=sr,
        output_directory=out_dir,
        base_name="test_song",
        original_metadata=meta,
        match_original_sample_rate=True
    )

    print(f"[✓] {len(exported_files)} arquivos WAV exportados:")
    for path in exported_files:
        info = sf.info(path)
        print(f"  • {os.path.basename(path)}: SR={info.samplerate}Hz, Subtype={info.subtype}, Canais={info.channels}, Duração={info.duration:.2f}s")
        assert info.format == "WAV", "Formato deve ser WAV!"
        assert info.samplerate == 48000, "Taxa de amostragem reconstruída deve coincidir com o original!"
        assert info.subtype in ("PCM_24", "FLOAT"), "Bit depth de alta resolução deve ser preservado!"

    print("\n==========================================================")
    print("   [✓✓✓] TODOS OS TESTES PASSARAM COM SUCESSO!            ")
    print("==========================================================")


if __name__ == "__main__":
    main()
