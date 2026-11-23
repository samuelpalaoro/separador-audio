"""Audio exporter module maintaining absolute audio fidelity without lossy compression."""
import os
from typing import Dict, Any, Optional, Callable, List
import numpy as np
import soundfile as sf
import torch
import torchaudio.transforms as T


def get_compatible_subtype(original_subtype: Optional[str]) -> str:
    """
    Determine the most appropriate WAV subtype preserving bit depth.
    Defaults to 24-bit PCM or 32-bit Float if original was high-res.
    """
    if not original_subtype:
        return "PCM_24"
    
    sub = original_subtype.upper()
    if "FLOAT" in sub or "32" in sub and "FLOAT" in sub:
        return "FLOAT"
    elif "PCM_32" in sub:
        return "PCM_32"
    elif "PCM_24" in sub:
        return "PCM_24"
    elif "PCM_16" in sub:
        return "PCM_16"
    elif "DOUBLE" in sub:
        return "DOUBLE"
    
    # Default high-fidelity subtype
    return "PCM_24"


def sanitize_stem_slug(stem_name: str) -> str:
    """
    Generate clean, standard filename stem identifiers.
    Examples:
        'Vocals (Voz)' -> 'vocals'
        'Drums (Bateria)' -> 'drums'
        'Bass (Baixo)' -> 'bass'
        'Other (Outros)' -> 'other'
        'Guitar (Guitarra)' -> 'guitar'
        'Piano' -> 'piano'
    """
    s = stem_name.lower()
    if "vocal" in s or "voz" in s:
        return "vocals"
    elif "drum" in s or "bater" in s:
        return "drums"
    elif "bass" in s or "baixo" in s:
        return "bass"
    elif "guitar" in s or "viol" in s:
        return "guitar"
    elif "piano" in s or "teclado" in s:
        return "piano"
    elif "other" in s or "outro" in s:
        return "other"
    # General cleanup
    cleaned = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in s)
    return cleaned.strip("_")


def export_stem_to_wav(
    stem_audio: np.ndarray,
    stem_sample_rate: int,
    output_path: str,
    original_metadata: Optional[Dict[str, Any]] = None,
    match_original_sample_rate: bool = False
) -> str:
    """
    Export a single audio stem to uncompressed WAV format.
    
    Parameters:
    - stem_audio: numpy array of shape (samples, channels) with float32 values [-1.0, 1.0].
    - stem_sample_rate: sampling rate of stem_audio (Demucs outputs at 44100 Hz).
    - output_path: destination file path (.wav).
    - original_metadata: metadata dict of the source WAV file.
    - match_original_sample_rate: if True and source SR != model SR, resamples using high-quality sinc.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Ensure correct numpy dimensions (samples, channels)
    audio = np.asarray(stem_audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio[:, np.newaxis]
    elif audio.ndim == 2 and audio.shape[0] < audio.shape[1] and audio.shape[0] <= 2:
        # Transposed (channels, samples) -> (samples, channels)
        audio = audio.T

    target_sr = stem_sample_rate
    target_subtype = "PCM_24"  # Default high resolution
    
    if original_metadata:
        orig_sr = original_metadata.get("samplerate")
        orig_subtype = original_metadata.get("subtype")
        orig_channels = original_metadata.get("channels", 2)
        orig_frames = original_metadata.get("frames")
        
        target_subtype = get_compatible_subtype(orig_subtype)
        
        # If user requested matching original sample rate and they differ
        if match_original_sample_rate and orig_sr and orig_sr != stem_sample_rate:
            # High-quality sinc resampling via torchaudio
            tensor_audio = torch.from_numpy(audio.T)  # (channels, samples)
            resampler = T.Resample(orig_freq=stem_sample_rate, new_freq=orig_sr, resampling_method="sinc_interp_hann")
            resampled_tensor = resampler(tensor_audio)
            audio = resampled_tensor.numpy().T
            target_sr = orig_sr
            
            # Align exact frame count with original to prevent rounding sample drift
            if orig_frames and orig_frames > 0:
                if audio.shape[0] > orig_frames:
                    audio = audio[:orig_frames, :]
                elif audio.shape[0] < orig_frames:
                    pad = orig_frames - audio.shape[0]
                    audio = np.pad(audio, ((0, pad), (0, 0)), mode="constant")
            
        # If original audio was mono (1 channel), preserve 1 channel
        if orig_channels == 1 and audio.shape[1] == 2:
            # Average left and right to preserve mono without phase distortion
            audio = np.mean(audio, axis=1, keepdims=True)

    # Note on Audio Quality:
    # No dynamic range compression, no lossy encoding, no arbitrary volume normalization.
    # Preserve exact dynamics produced by the neural network.
    # To prevent digital clipping on fixed-point formats (PCM_16, PCM_24), clamp values to [-1.0, 1.0].
    if target_subtype in ("PCM_16", "PCM_24", "PCM_32"):
        audio = np.clip(audio, -1.0, 1.0)
        
    sf.write(
        output_path,
        audio,
        samplerate=target_sr,
        subtype=target_subtype,
        format="WAV"
    )
    
    return output_path


def export_all_stems(
    stems: Dict[str, np.ndarray],
    stem_sample_rate: int,
    output_directory: str,
    base_name: str,
    original_metadata: Optional[Dict[str, Any]] = None,
    match_original_sample_rate: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[str]:
    """
    Export all stems to uncompressed WAV files in output_directory.
    Returns list of generated file paths.
    """
    os.makedirs(output_directory, exist_ok=True)
    exported_files = []
    
    total = len(stems)
    for idx, (stem_name, audio_data) in enumerate(stems.items()):
        stem_slug = sanitize_stem_slug(stem_name)
        filename = f"{base_name}_{stem_slug}.wav"
        out_path = os.path.join(output_directory, filename)
        
        export_stem_to_wav(
            stem_audio=audio_data,
            stem_sample_rate=stem_sample_rate,
            output_path=out_path,
            original_metadata=original_metadata,
            match_original_sample_rate=match_original_sample_rate
        )
        exported_files.append(out_path)
        
        if progress_callback:
            progress_callback(idx + 1, total, stem_name)
            
    return exported_files
