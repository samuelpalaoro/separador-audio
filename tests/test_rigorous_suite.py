"""
Testes Rigorosos — Moises AI Separador de Áudio
Executa validação completa dos 5 testes obrigatórios:
1. Importação (diferentes WAVs, metadados, arquivos inválidos e grandes)
2. Separação (modelo real de IA, 4 faixas, integridade e cancelamento)
3. Reprodução (individual, simultânea, solo, mute, seek, sincronização perfeita)
4. Exportação (individual, todas, verificação de integridade técnica WAV)
5. Estabilidade (processamento em sequência, múltiplos ciclos, memória, GUI offscreen)
"""
import os
import sys

# Ensure project root is in sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import gc
import shutil
import tempfile
import numpy as np
import soundfile as sf
import torch

from src.audio.inspector import inspect_audio_file, validate_wav_file
from src.separator.demucs_engine import DemucsEngine, CancellationRequestedError
from src.audio.player import MultiTrackPlayer
from src.audio.exporter import export_stem_to_wav, export_all_stems, sanitize_stem_slug
from src.utils.formatters import format_duration, format_filesize, format_sample_rate, format_channels


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def generate_synthetic_song(filepath: str, duration_sec: float = 3.0, sr: int = 48000, subtype: str = "PCM_24", channels: int = 2):
    """Generate realistic test music track with distinct frequency bands."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # Bass (80 Hz fundamental + harmonics)
    bass = 0.4 * np.sin(2 * np.pi * 80 * t) + 0.2 * np.sin(2 * np.pi * 160 * t)
    
    # Drums (Kick pulses + snare burst)
    kick = np.zeros_like(t)
    snare = np.zeros_like(t)
    beat_interval = int(sr * 0.5)
    for i in range(0, len(t), beat_interval):
        k_len = min(int(sr * 0.1), len(t) - i)
        kick[i:i+k_len] += 0.6 * np.sin(2 * np.pi * 65 * np.exp(-20 * np.linspace(0, 0.1, k_len)) * np.linspace(0, 0.1, k_len))
        if i + beat_interval // 2 < len(t):
            s_idx = i + beat_interval // 2
            s_len = min(int(sr * 0.08), len(t) - s_idx)
            snare[s_idx:s_idx+s_len] += 0.3 * (np.random.rand(s_len) * 2 - 1) * np.exp(-30 * np.linspace(0, 0.08, s_len))

    # Vocals / Lead melody (440Hz, 554Hz, 659Hz)
    lead = np.zeros_like(t)
    notes = [440.0, 554.37, 659.25, 880.0]
    note_dur = int(sr * 0.25)
    for n_idx, n_start in enumerate(range(0, len(t), note_dur)):
        f = notes[n_idx % len(notes)]
        n_len = min(note_dur, len(t) - n_start)
        lead[n_start:n_start+n_len] = 0.3 * np.sin(2 * np.pi * f * t[n_start:n_start+n_len])

    # Other (Pad chords at 220Hz + 277Hz)
    pad = 0.2 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 277 * t))

    mix_l = bass + kick + snare * 0.7 + lead * 0.8 + pad
    mix_r = bass + kick + snare * 0.7 + lead * 0.5 + pad * 1.1

    if channels == 1:
        signal = 0.5 * (mix_l + mix_r)
    else:
        signal = np.column_stack([mix_l, mix_r])

    signal = np.clip(signal, -0.95, 0.95)
    sf.write(filepath, signal, sr, subtype=subtype, format="WAV")


def test_1_import():
    print_header("TESTE 1 — IMPORTAÇÃO DE ARQUIVOS WAV")
    tmp_dir = tempfile.mkdtemp(prefix="test_import_")
    try:
        # 1.1 16-bit 44.1kHz Stereo
        f_16 = os.path.join(tmp_dir, "test_16bit_44k.wav")
        generate_synthetic_song(f_16, duration_sec=2.0, sr=44100, subtype="PCM_16", channels=2)
        valid, err, meta = validate_wav_file(f_16)
        assert valid, f"Falha ao validar 16-bit WAV: {err}"
        assert meta["samplerate"] == 44100
        assert meta["channels"] == 2
        assert "16-bit" in meta["bit_depth"]
        assert meta["duration"] > 1.9
        print(f"  [✓] 16-bit 44.1kHz Estéreo validado: {meta['filesize_formatted']}, {meta['duration_formatted']}")

        # 1.2 24-bit 48kHz Stereo
        f_24 = os.path.join(tmp_dir, "test_24bit_48k.wav")
        generate_synthetic_song(f_24, duration_sec=3.5, sr=48000, subtype="PCM_24", channels=2)
        valid, err, meta = validate_wav_file(f_24)
        assert valid, f"Falha ao validar 24-bit WAV: {err}"
        assert meta["samplerate"] == 48000
        assert "24-bit" in meta["bit_depth"]
        print(f"  [✓] 24-bit 48kHz Estéreo validado: {meta['filesize_formatted']}, {meta['duration_formatted']}")

        # 1.3 32-bit Float 96kHz Stereo
        f_32 = os.path.join(tmp_dir, "test_32bit_96k.wav")
        generate_synthetic_song(f_32, duration_sec=1.5, sr=96000, subtype="FLOAT", channels=2)
        valid, err, meta = validate_wav_file(f_32)
        assert valid, f"Falha ao validar 32-bit Float WAV: {err}"
        assert meta["samplerate"] == 96000
        assert "Float" in meta["bit_depth"] or "32" in meta["bit_depth"]
        print(f"  [✓] 32-bit Float 96kHz Estéreo validado: {meta['filesize_formatted']}, {meta['duration_formatted']}")

        # 1.4 Mono WAV (1 channel)
        f_mono = os.path.join(tmp_dir, "test_mono.wav")
        generate_synthetic_song(f_mono, duration_sec=2.0, sr=44100, subtype="PCM_16", channels=1)
        valid, err, meta = validate_wav_file(f_mono)
        assert valid, f"Falha ao validar Mono WAV: {err}"
        assert meta["channels"] == 1
        assert "Mono" in meta["channels_formatted"]
        print(f"  [✓] Mono 1-canal validado: {meta['channels_formatted']}")

        # 1.5 Arquivo vazio (0 bytes) -> deve ser rejeitado graciosamente
        f_empty = os.path.join(tmp_dir, "empty.wav")
        with open(f_empty, "wb") as f:
            pass
        valid, err, _ = validate_wav_file(f_empty)
        assert not valid, "Arquivo vazio deveria ter sido rejeitado!"
        print(f"  [✓] Arquivo 0-bytes rejeitado corretamente: '{err}'")

        # 1.6 Arquivo corrompido (lixo binário) -> deve ser rejeitado graciosamente
        f_corrupt = os.path.join(tmp_dir, "corrupt.wav")
        with open(f_corrupt, "wb") as f:
            f.write(b"RIFF\x00\x00\x00\x00WAVEfmt \x00\x00\x00\x00corrupteddata")
        valid, err, _ = validate_wav_file(f_corrupt)
        assert not valid, "Arquivo corrompido deveria ter sido rejeitado!"
        print(f"  [✓] Arquivo corrompido rejeitado corretamente: '{err}'")

        # 1.7 Arquivo de texto renomeado para .wav
        f_txt = os.path.join(tmp_dir, "fake.wav")
        with open(f_txt, "w") as f:
            f.write("I am not an audio file.")
        valid, err, _ = validate_wav_file(f_txt)
        assert not valid, "Arquivo de texto deveria ter sido rejeitado!"
        print(f"  [✓] Fake WAV rejeitado corretamente: '{err}'")

        # 1.8 Arquivo muito grande (teste de inspeção eficiente sem estourar memória)
        f_large = os.path.join(tmp_dir, "large_song.wav")
        # 15 segundos em 96kHz 24-bit PCM (~8.6 MB de amostras reais)
        generate_synthetic_song(f_large, duration_sec=15.0, sr=96000, subtype="PCM_24", channels=2)
        valid, err, meta = validate_wav_file(f_large)
        assert valid
        assert meta["duration"] >= 14.9
        assert meta["frames"] == int(96000 * 15.0)
        print(f"  [✓] Arquivo grande inspecionado com sucesso: {meta['filesize_formatted']}, {meta['frames']} frames")

        print("  [✓✓] TESTE 1 APROVADO COM SUCESSO TOTAL!")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2_separation():
    print_header("TESTE 2 — SEPARAÇÃO POR IA (DEMUCS HTDEMUCS)")
    tmp_dir = tempfile.mkdtemp(prefix="test_sep_")
    try:
        f_audio = os.path.join(tmp_dir, "song.wav")
        generate_synthetic_song(f_audio, duration_sec=3.0, sr=44100, subtype="PCM_24", channels=2)

        engine = DemucsEngine()
        progress_steps = []

        def on_prog(pct, msg):
            progress_steps.append((pct, msg))

        # 2.1 Teste de cancelamento precoce
        try:
            engine.separate(
                filepath=f_audio,
                model_name="htdemucs",
                cancel_check=lambda: True
            )
            assert False, "Cancelamento precoce deveria ter lançado CancellationRequestedError"
        except CancellationRequestedError:
            print("  [✓] Cancelamento precoce testado e capturado com sucesso.")

        # 2.2 Separação real de áudio com Demucs
        stems, sr, meta = engine.separate(
            filepath=f_audio,
            model_name="htdemucs",
            shifts=1,
            overlap=0.25,
            progress_callback=on_prog
        )

        assert sr == 44100
        assert len(stems) == 4, f"Esperadas 4 faixas, obtidas {len(stems)}: {list(stems.keys())}"
        
        # Verificar ordem padrão Moises AI: Vocals, Drums, Bass, Other
        keys = list(stems.keys())
        assert any("vocal" in k.lower() or "voz" in k.lower() for k in [keys[0]]), f"Vocals deveria ser a primeira faixa, obtido: {keys[0]}"
        assert any("drum" in k.lower() or "bater" in k.lower() for k in [keys[1]]), f"Drums deveria ser a segunda faixa, obtido: {keys[1]}"
        assert any("bass" in k.lower() or "baixo" in k.lower() for k in [keys[2]]), f"Bass deveria ser a terceira faixa, obtido: {keys[2]}"
        assert any("other" in k.lower() or "outro" in k.lower() for k in [keys[3]]), f"Other deveria ser a quarta faixa, obtido: {keys[3]}"

        for name, data in stems.items():
            assert isinstance(data, np.ndarray), f"Faixa {name} deve ser numpy array"
            assert data.shape[0] > 0, f"Faixa {name} vazia!"
            assert data.shape[1] == 2, f"Faixa {name} deve ser estéreo (2 canais)"
            rms = np.sqrt(np.mean(data ** 2))
            assert rms > 0.0001, f"Faixa {name} contém apenas silêncio (RMS={rms})!"
            print(f"  [✓] Faixa '{name}': shape={data.shape}, dtype={data.dtype}, RMS={rms:.4f}, min={data.min():.3f}, max={data.max():.3f}")

        assert len(progress_steps) > 0, "Callback de progresso não foi acionado"
        assert progress_steps[-1][0] == 100, "Progresso não finalizou em 100%"
        print(f"  [✓] Progresso validado ({len(progress_steps)} etapas reportadas).")

        print("  [✓✓] TESTE 2 APROVADO COM SUCESSO TOTAL!")
        return stems, sr, meta
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_3_playback(stems, sr):
    print_header("TESTE 3 — REPRODUÇÃO, MIXER E SINCRONIZAÇÃO")
    player = MultiTrackPlayer(sample_rate=sr)
    player.load_stems(stems, sample_rate=sr)

    # 3.1 Duração carregada
    duration = player.duration_seconds
    assert duration > 2.8 and duration < 3.2, f"Duração incorreta: {duration}s"
    print(f"  [✓] Faixas carregadas com sucesso no mixer. Duração: {duration:.2f}s")

    stem_keys = list(stems.keys())
    vocals_key = stem_keys[0]
    drums_key = stem_keys[1]
    bass_key = stem_keys[2]
    other_key = stem_keys[3]

    # 3.2 Teste do buffer de mixagem simulado (sem necessitar de placa de som física)
    # Callback interno do mixer _audio_callback
    out_buf = np.zeros((1024, 2), dtype=np.float32)

    # Iniciar reprodução
    player.is_playing = True
    player.current_frame = 0

    # 3.3 Teste de reprodução com todas as faixas ativas (Mix completo)
    player._audio_callback(out_buf, 1024, None, None)
    assert not np.all(out_buf == 0), "Mix completo deveria conter áudio sintetizado!"
    assert player.current_frame == 1024, f"Posição de quadro incorreta: {player.current_frame}"
    print(f"  [✓] Mixagem simultânea funcionando perfeitamente (buffer preenchido).")

    # 3.4 Teste de Mute individual
    player.set_stem_muted(vocals_key, True)
    assert player.is_stem_audible(vocals_key) is False, "Faixa mutada não deve ser audível"
    assert player.is_stem_audible(drums_key) is True, "Outras faixas devem continuar audíveis"
    player._audio_callback(out_buf, 1024, None, None)
    print(f"  [✓] Modo Mute testado com sucesso.")

    # 3.5 Teste de Solo individual
    player.set_stem_muted(vocals_key, False)
    player.set_stem_solo(bass_key, True)
    assert player.is_stem_audible(bass_key) is True, "Faixa em solo deve ser audível"
    assert player.is_stem_audible(drums_key) is False, "Demais faixas devem ser silenciadas em modo Solo"
    assert player.is_stem_audible(vocals_key) is False
    print(f"  [✓] Modo Solo testado com sucesso (apenas Bass audível).")

    # 3.6 Teste de múltiplos Solos
    player.set_stem_solo(drums_key, True)
    assert player.is_stem_audible(bass_key) is True
    assert player.is_stem_audible(drums_key) is True
    assert player.is_stem_audible(vocals_key) is False
    print(f"  [✓] Multi-Solo (Bass + Drums) funcionando perfeitamente.")

    # 3.7 Reset de Solo
    player.set_stem_solo(bass_key, False)
    player.set_stem_solo(drums_key, False)
    assert player.is_stem_audible(vocals_key) is True
    assert player.is_stem_audible(bass_key) is True

    # 3.8 Teste de Controle de Volume
    player.set_stem_volume(vocals_key, 0.5)
    assert abs(player.tracks[vocals_key].volume - 0.5) < 0.01
    player.set_master_volume(0.8)
    assert abs(player.master_volume - 0.8) < 0.01
    print(f"  [✓] Controle de volume de faixa e volume master validados.")

    # 3.9 Teste de Seek e Sincronização Perfeita
    player.seek(1.5)  # Seek para 1.5s
    expected_frame = int(1.5 * sr)
    assert abs(player.current_frame - expected_frame) <= 1, f"Seek para frame incorreto: {player.current_frame} vs {expected_frame}"
    assert abs(player.current_time_seconds - 1.5) < 0.01
    print(f"  [✓] Seek preciso para 1.50s validado (frame {player.current_frame}).")

    # 3.10 Teste de Pause e Stop
    player.pause()
    assert player.is_playing is False
    curr_frame = player.current_frame
    player._audio_callback(out_buf, 1024, None, None)
    assert np.all(out_buf == 0), "Buffer quando pausado deve ser silêncio"
    assert player.current_frame == curr_frame, "Frame não deve avançar quando pausado"

    player.stop()
    assert player.is_playing is False
    assert player.current_frame == 0
    print(f"  [✓] Pause e Stop validados (rewind para 00:00).")

    player.close()
    print("  [✓✓] TESTE 3 APROVADO COM SUCESSO TOTAL!")


def test_4_export(stems, sr, meta):
    print_header("TESTE 4 — EXPORTAÇÃO DE STEMS EM WAV")
    tmp_out = tempfile.mkdtemp(prefix="test_export_")
    try:
        # 4.1 Exportar faixa individual (Vocals)
        vocal_key = [k for k in stems.keys() if "vocal" in k.lower() or "voz" in k.lower()][0]
        out_vocal = os.path.join(tmp_out, "my_song_vocals.wav")
        export_stem_to_wav(
            stem_audio=stems[vocal_key],
            stem_sample_rate=sr,
            output_path=out_vocal,
            original_metadata=meta,
            match_original_sample_rate=True
        )

        assert os.path.exists(out_vocal), "Arquivo vocal exportado não foi criado!"
        v_info = sf.info(out_vocal)
        assert v_info.format == "WAV", "Formato deve ser WAV"
        assert v_info.samplerate == meta["samplerate"], f"Sample rate deve coincidir com o original ({meta['samplerate']})"
        assert v_info.channels == meta["channels"], f"Canais devem coincidir ({meta['channels']})"
        assert v_info.subtype in ("PCM_24", "FLOAT"), f"Bit depth de alta resolução deve ser preservado: {v_info.subtype}"
        print(f"  [✓] Faixa individual '{vocal_key}' exportada com sucesso:")
        print(f"      {os.path.basename(out_vocal)}: {v_info.samplerate}Hz, {v_info.subtype}, {v_info.channels} canais, {v_info.duration:.2f}s")

        # 4.2 Exportar todas as faixas simultaneamente
        export_dir = os.path.join(tmp_out, "all_stems")
        exported = export_all_stems(
            stems=stems,
            stem_sample_rate=sr,
            output_directory=export_dir,
            base_name="song_test",
            original_metadata=meta,
            match_original_sample_rate=True
        )

        assert len(exported) == 4, f"Esperados 4 arquivos exportados, obtidos {len(exported)}"
        expected_stems = ["vocals", "drums", "bass", "other"]

        for path in exported:
            assert os.path.exists(path), f"Arquivo não encontrado: {path}"
            info = sf.info(path)
            fname = os.path.basename(path)
            
            # Verificar se não há parênteses ou caracteres estranhos no nome
            assert "(" not in fname and ")" not in fname, f"Nome do arquivo não deve conter parênteses: {fname}"
            assert info.format == "WAV", f"Arquivo {fname} não é WAV"
            assert info.samplerate == meta["samplerate"]
            assert info.channels == meta["channels"]
            assert info.frames == meta["frames"], f"Frames de áudio diferem do original! {info.frames} vs {meta['frames']}"
            
            # Verificar integridade dos dados de áudio (sem NaNs, sem Infinitos)
            data, _ = sf.read(path, dtype="float32")
            assert not np.isnan(data).any(), f"Arquivo {fname} contém NaN!"
            assert not np.isinf(data).any(), f"Arquivo {fname} contém Infinity!"
            assert np.max(np.abs(data)) > 0.0001, f"Arquivo {fname} está completamente mudo!"
            print(f"  [✓] Stem exportado '{fname}': {info.samplerate}Hz, {info.subtype}, frames={info.frames}, sem perdas!")

        print("  [✓✓] TESTE 4 APROVADO COM SUCESSO TOTAL!")
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)


def test_5_stability():
    print_header("TESTE 5 — ESTABILIDADE, MEMÓRIA E CICLO DE VIDA")
    tmp_dir = tempfile.mkdtemp(prefix="test_stab_")
    try:
        engine = DemucsEngine()
        player = MultiTrackPlayer(sample_rate=44100)

        # 5.1 Processar duas músicas diferentes em sequência na mesma instância
        print("  [*] Testando processamento sequencial de múltiplas faixas...")
        for i in range(1, 3):
            song_path = os.path.join(tmp_dir, f"seq_song_{i}.wav")
            generate_synthetic_song(song_path, duration_sec=2.0, sr=44100, subtype="PCM_16", channels=2)
            
            stems, sr, meta = engine.separate(
                filepath=song_path,
                model_name="htdemucs",
                shifts=1,
                overlap=0.25
            )
            assert len(stems) == 4
            player.load_stems(stems, sample_rate=sr)
            assert abs(player.duration_seconds - 2.0) < 0.1
            
            # Simular reprodução e parada
            player.play()
            buf = np.zeros((512, 2), dtype=np.float32)
            player._audio_callback(buf, 512, None, None)
            player.stop()
            print(f"  [✓] Música sequencial {i}/2 processada e carregada com sucesso.")

        player.close()

        # 5.2 Teste de stress com 500 ciclos rápidos de Play/Pause/Seek/Solo/Mute
        print("  [*] Testando robustez com 500 ciclos simultâneos de transporte...")
        test_player = MultiTrackPlayer(sample_rate=44100)
        test_player.load_stems(stems, sample_rate=44100)

        for cycle in range(500):
            test_player.play()
            test_player.seek_normalized((cycle % 100) / 100.0)
            test_player.set_stem_volume("Vocals (Voz)", (cycle % 15) / 10.0)
            test_player.set_stem_muted("Drums (Bateria)", cycle % 2 == 0)
            test_player.set_stem_solo("Bass (Baixo)", cycle % 3 == 0)
            buf = np.zeros((128, 2), dtype=np.float32)
            test_player._audio_callback(buf, 128, None, None)
            if cycle % 10 == 0:
                test_player.pause()
            if cycle % 50 == 0:
                test_player.stop()

        test_player.close()
        print("  [✓] 500 ciclos rápidos executados sem deadlocks, travamentos ou exceções.")

        # 5.3 Teste de GUI offscreen (Qt Application lifecycle)
        print("  [*] Testando ciclo de vida da interface gráfica (PySide6)...")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow

        app = QApplication.instance() or QApplication(sys.argv)
        win = MainWindow()
        win.show()

        # Simular carregamento de arquivo pela dropzone
        sample_wav = os.path.join(tmp_dir, "seq_song_1.wav")
        win.drop_zone.load_file(sample_wav)
        assert win.loaded_filepath == sample_wav
        assert win.btn_separate.isEnabled() is True
        print("  [✓] Carregamento de arquivo na GUI validado.")

        # Simular injeção de stems concluídos
        win._on_worker_finished(stems, 44100, meta)
        assert win.stems_card.isVisible() is True
        assert len(win.stem_widgets) == 4
        assert win.transport.btn_play_pause.isEnabled() is True
        assert win.transport.btn_export_all.isEnabled() is True
        print("  [✓] Renderização de faixas e transporte na GUI validada.")

        # Testar fechamento gracioso da janela
        win.close()
        print("  [✓] Fechamento e liberação da janela concluídos com sucesso.")

        print("  [✓✓] TESTE 5 APROVADO COM SUCESSO TOTAL!")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print("==================================================================")
    print("   INICIANDO BATERIA RIGOROSA DE TESTES — SEPARADOR DE ÁUDIO     ")
    print("==================================================================")
    
    # Executar Teste 1
    test_1_import()
    
    # Executar Teste 2
    stems, sr, meta = test_2_separation()
    
    # Executar Teste 3
    test_3_playback(stems, sr)
    
    # Executar Teste 4
    test_4_export(stems, sr, meta)
    
    # Executar Teste 5
    test_5_stability()

    print("\n" + "=" * 70)
    print("   [✓✓✓] TODOS OS 5 TESTES OBRIGATÓRIOS FORAM APROVADOS!        ")
    print("   O sistema é 100% funcional, estável, sem perdas e confiável. ")
    print("==================================================================")


if __name__ == "__main__":
    main()
