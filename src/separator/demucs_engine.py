"""Demucs AI Audio Separation Engine."""
import os
import math
from typing import Dict, List, Tuple, Any, Optional, Callable
import numpy as np
import soundfile as sf
import torch
import torchaudio.transforms as T
import demucs.pretrained
from demucs.apply import apply_model
from src.audio.inspector import inspect_audio_file


class CancellationRequestedError(Exception):
    """Exception raised when user requests cancellation of separation."""
    pass


class DemucsEngine:
    """Manages Demucs model loading and audio stem separation."""
    
    MODELS = {
        "htdemucs": {
            "name": "HTDemucs (Padrão - 4 Faixas)",
            "description": "Excelente equilíbrio entre qualidade e velocidade. Separa em Voz, Bateria, Baixo e Outros.",
            "stems": ["vocals", "drums", "bass", "other"],
            "stems_count": 4
        },
        "htdemucs_ft": {
            "name": "HTDemucs Fine-Tuned (Alta Fidelidade - 4 Faixas)",
            "description": "Versão refinada para máxima precisão sonora. Separa em Voz, Bateria, Baixo e Outros.",
            "stems": ["vocals", "drums", "bass", "other"],
            "stems_count": 4
        },
        "htdemucs_6s": {
            "name": "HTDemucs 6 Faixas (Voz, Bateria, Baixo, Guitarra, Piano, Outros)",
            "description": "Isolamento avançado de 6 faixas, incluindo Piano e Guitarra.",
            "stems": ["vocals", "drums", "bass", "other", "guitar", "piano"],
            "stems_count": 6
        },
        "mdx_extra": {
            "name": "MDX-Extra (4 Faixas)",
            "description": "Arquitetura baseada em MDX-Net, recomendada para vocais densos.",
            "stems": ["vocals", "drums", "bass", "other"],
            "stems_count": 4
        }
    }

    def __init__(self):
        self._cached_models: Dict[str, Any] = {}
        self._current_device: Optional[torch.device] = None

    @classmethod
    def get_model_choices(cls) -> List[Tuple[str, str, str]]:
        """Return list of (model_id, display_name, description)."""
        return [
            (model_id, meta["name"], meta["description"])
            for model_id, meta in cls.MODELS.items()
        ]

    def get_device(self, preferred_device: Optional[str] = None) -> torch.device:
        """Resolve target PyTorch device (CUDA or CPU)."""
        if preferred_device:
            return torch.device(preferred_device)
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def load_model(self, model_name: str, device: Optional[torch.device] = None):
        """Load pretrained model with caching and automatic download if needed."""
        if model_name not in self.MODELS:
            model_name = "htdemucs"
            
        target_device = device or self.get_device()
        cache_key = f"{model_name}_{target_device.type}"
        
        if cache_key in self._cached_models:
            return self._cached_models[cache_key]
            
        model = demucs.pretrained.get_model(model_name)
        model.to(target_device)
        model.eval()
        
        self._cached_models[cache_key] = model
        return model

    def separate(
        self,
        filepath: str,
        model_name: str = "htdemucs",
        device_name: Optional[str] = None,
        shifts: int = 1,
        overlap: float = 0.25,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Tuple[Dict[str, np.ndarray], int, Dict[str, Any]]:
        """
        Execute audio separation on the given audio file.
        
        Returns:
            (stems_dict, sample_rate, original_metadata)
            where stems_dict maps stem_name (e.g. 'Vocals', 'Drums') to float32 numpy array (samples, channels).
        """
        if cancel_check and cancel_check():
            raise CancellationRequestedError("Processamento cancelado antes do início.")

        if progress_callback:
            progress_callback(5, "Inspecionando arquivo de áudio...")

        meta = inspect_audio_file(filepath)
        target_device = self.get_device(device_name)

        if progress_callback:
            device_label = "GPU NVIDIA (CUDA)" if target_device.type == "cuda" else "Processador (CPU)"
            progress_callback(10, f"Carregando modelo {model_name} no dispositivo {device_label}...")

        model = self.load_model(model_name, target_device)

        if cancel_check and cancel_check():
            raise CancellationRequestedError("Processamento cancelado pelo usuário.")

        if progress_callback:
            progress_callback(20, "Carregando dados de áudio em alta resolução...")

        # Load audio with soundfile to preserve exact bits
        audio_data, file_sr = sf.read(filepath, dtype="float32", always_2d=True)
        # audio_data shape: (samples, channels)
        
        # Prepare tensor of shape (channels, samples)
        wav_tensor = torch.from_numpy(audio_data.T)

        # Ensure stereo (Demucs expects 2 channels)
        if wav_tensor.shape[0] == 1:
            wav_tensor = wav_tensor.repeat(2, 1)
        elif wav_tensor.shape[0] > 2:
            wav_tensor = wav_tensor[:2, :]

        # If sample rate differs from Demucs requirement (44100 Hz), resample tensor with sinc
        model_sr = getattr(model, "samplerate", 44100)
        if file_sr != model_sr:
            if progress_callback:
                progress_callback(25, f"Adequando taxa de amostragem ({file_sr} Hz -> {model_sr} Hz)...")
            resampler = T.Resample(orig_freq=file_sr, new_freq=model_sr, resampling_method="sinc_interp_hann")
            wav_tensor = resampler(wav_tensor)

        total_audio_length = wav_tensor.shape[-1]
        
        # Segment and chunk tracking for progress reporting
        segment_len = int(getattr(model, "segment", 7.8) * model_sr)
        stride = int((1.0 - overlap) * segment_len) if segment_len > 0 else model_sr
        total_steps = max(1, math.ceil(total_audio_length / stride)) * shifts

        current_step = 0

        def apply_callback(info: dict):
            nonlocal current_step
            if cancel_check and cancel_check():
                raise CancellationRequestedError("Processamento interrompido pelo usuário.")

            state = info.get("state")
            if state == "end":
                current_step += 1
                pct = min(90, 30 + int((current_step / max(1, total_steps)) * 60))
                if progress_callback:
                    progress_callback(pct, f"Processando separação por IA... ({pct}%)")

        if progress_callback:
            progress_callback(30, "Iniciando separação neural das faixas...")

        sources = None
        try:
            wav_tensor = wav_tensor.unsqueeze(0).to(target_device)  # (1, channels, samples)

            with torch.no_grad():
                try:
                    sources = apply_model(
                        model=model,
                        mix=wav_tensor,
                        shifts=shifts,
                        split=True,
                        overlap=overlap,
                        device=target_device,
                        progress=False,
                        callback=apply_callback
                    )
                except Exception as e:
                    if cancel_check and cancel_check():
                        raise CancellationRequestedError("Processamento interrompido pelo usuário.")
                    raise e

            if progress_callback:
                progress_callback(92, "Organizando faixas separadas...")

            # sources shape: (1, num_sources, channels, samples)
            sources = sources.squeeze(0).cpu()  # (num_sources, channels, samples)

            model_sources = getattr(model, "sources", ["drums", "bass", "other", "vocals"])
            raw_stems: Dict[str, np.ndarray] = {}

            # Friendly English/Portuguese naming map
            name_map = {
                "vocals": "Vocals (Voz)",
                "drums": "Drums (Bateria)",
                "bass": "Bass (Baixo)",
                "other": "Other (Outros)",
                "guitar": "Guitar (Guitarra)",
                "piano": "Piano"
            }

            for idx, src_name in enumerate(model_sources):
                stem_key = src_name.lower()
                stem_label = name_map.get(stem_key, src_name.capitalize())
                # Convert (channels, samples) -> (samples, channels) float32 numpy
                stem_audio = sources[idx].numpy().T
                raw_stems[stem_key] = (stem_label, stem_audio)

            # Re-order stems into standard Moises order: Vocals, Drums, Bass, Other, Guitar, Piano
            desired_order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
            stems_dict: Dict[str, np.ndarray] = {}
            for key in desired_order:
                if key in raw_stems:
                    label, audio = raw_stems[key]
                    stems_dict[label] = audio
            # Add any remaining
            for key, (label, audio) in raw_stems.items():
                if label not in stems_dict:
                    stems_dict[label] = audio

            if progress_callback:
                progress_callback(100, "Separação concluída com sucesso!")

            return stems_dict, model_sr, meta

        finally:
            try:
                del wav_tensor
            except Exception:
                pass
            if sources is not None:
                try:
                    del sources
                except Exception:
                    pass
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            import gc
            gc.collect()
