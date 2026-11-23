"""Multi-track synchronized audio player engine using sounddevice."""
import os
import sys
import threading
import time
import ctypes.util
from typing import Dict, Optional, Callable
import numpy as np

# Ensure PortAudio library is located
_local_portaudio = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "lib", "usr", "lib", "x86_64-linux-gnu", "libportaudio.so.2")
)
_orig_find_library = ctypes.util.find_library

def _portaudio_find_library(name: str):
    if name in ("portaudio", "libportaudio", "libportaudio.so"):
        if os.path.exists(_local_portaudio):
            return _local_portaudio
    return _orig_find_library(name)

ctypes.util.find_library = _portaudio_find_library

import sounddevice as sd


class StemTrack:
    """Represents a single audio stem track with independent controls."""
    def __init__(self, name: str, audio_data: np.ndarray):
        self.name = name
        # Audio data is expected to be shape (samples, channels) float32
        data = np.asarray(audio_data, dtype=np.float32)
        if data.ndim == 1:
            data = data[:, np.newaxis]
        elif data.ndim == 2 and data.shape[0] < data.shape[1] and data.shape[0] <= 2:
            data = data.T
        self.data = data
        self.volume = 1.0       # 0.0 to 1.5
        self.is_muted = False
        self.is_solo = False


class MultiTrackPlayer:
    """
    Real-time multi-track mixer and player engine.
    Guarantees sample-accurate synchronization across all stems.
    """
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.tracks: Dict[str, StemTrack] = {}
        self.total_frames = 0
        self.current_frame = 0
        
        self.is_playing = False
        self.master_volume = 1.0
        
        self.stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()
        
        # Position notification callback: callback(current_time_sec, total_time_sec)
        self.on_position_update: Optional[Callable[[float, float], None]] = None
        self.on_playback_finished: Optional[Callable[[], None]] = None
        
        # Monitor thread for smooth UI updates
        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def load_stems(self, stems_dict: Dict[str, np.ndarray], sample_rate: int = 44100):
        """Load or replace stems for playback."""
        self.stop()
        with self._lock:
            self.sample_rate = sample_rate
            self.tracks.clear()
            max_frames = 0
            
            for name, audio in stems_dict.items():
                track = StemTrack(name, audio)
                self.tracks[name] = track
                if track.data.shape[0] > max_frames:
                    max_frames = track.data.shape[0]
                    
            self.total_frames = max_frames
            self.current_frame = 0

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate and self.total_frames > 0:
            return float(self.total_frames) / float(self.sample_rate)
        return 0.0

    @property
    def current_time_seconds(self) -> float:
        if self.sample_rate and self.total_frames > 0:
            return float(self.current_frame) / float(self.sample_rate)
        return 0.0

    def set_stem_volume(self, stem_name: str, volume: float):
        """Set stem volume (0.0 to 1.5)."""
        with self._lock:
            if stem_name in self.tracks:
                self.tracks[stem_name].volume = max(0.0, min(float(volume), 2.0))

    def set_stem_muted(self, stem_name: str, muted: bool):
        """Toggle mute for a stem."""
        with self._lock:
            if stem_name in self.tracks:
                self.tracks[stem_name].is_muted = bool(muted)

    def set_stem_solo(self, stem_name: str, solo: bool):
        """Toggle solo for a stem."""
        with self._lock:
            if stem_name in self.tracks:
                self.tracks[stem_name].is_solo = bool(solo)

    def set_master_volume(self, volume: float):
        """Set master volume (0.0 to 1.5)."""
        with self._lock:
            self.master_volume = max(0.0, min(float(volume), 2.0))

    def seek(self, seconds: float):
        """Seek to specific position in seconds."""
        with self._lock:
            target_frame = int(round(seconds * self.sample_rate))
            self.current_frame = max(0, min(target_frame, self.total_frames))
        if self.on_position_update:
            self.on_position_update(self.current_time_seconds, self.duration_seconds)

    def seek_normalized(self, fraction: float):
        """Seek by normalized fraction (0.0 to 1.0)."""
        target_sec = max(0.0, min(fraction, 1.0)) * self.duration_seconds
        self.seek(target_sec)

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """Real-time sounddevice output buffer callback."""
        with self._lock:
            if not self.is_playing or self.current_frame >= self.total_frames:
                outdata.fill(0)
                if self.is_playing and self.current_frame >= self.total_frames:
                    self.is_playing = False
                    self.current_frame = 0
                    if self.on_playback_finished:
                        threading.Thread(target=self.on_playback_finished, daemon=True).start()
                return

            start_f = self.current_frame
            end_f = min(start_f + frames, self.total_frames)
            actual_frames = end_f - start_f

            # Determine solo active state
            solo_tracks = [t for t in self.tracks.values() if t.is_solo]
            has_solo = len(solo_tracks) > 0

            # Buffer for mixed output (channels=2)
            mixed = np.zeros((actual_frames, 2), dtype=np.float32)

            for track in self.tracks.values():
                # If solo is active, ignore tracks not marked as solo
                if has_solo and not track.is_solo:
                    continue
                # If muted (and not overriding via solo), skip
                if not has_solo and track.is_muted:
                    continue
                if track.volume <= 0.001:
                    continue

                track_end = min(end_f, track.data.shape[0])
                if start_f < track_end:
                    track_chunk = track.data[start_f:track_end]
                    effective_gain = track.volume * self.master_volume
                    
                    if track_chunk.shape[1] == 1:
                        # Mono track broadcasted to stereo
                        mixed[:track_chunk.shape[0], 0] += track_chunk[:, 0] * effective_gain
                        mixed[:track_chunk.shape[0], 1] += track_chunk[:, 0] * effective_gain
                    else:
                        # Stereo track
                        mixed[:track_chunk.shape[0], :] += track_chunk[:, :2] * effective_gain

            # Soft limiter / clipping protection for playback only
            np.clip(mixed, -1.0, 1.0, out=mixed)

            outdata[:actual_frames] = mixed
            if actual_frames < frames:
                outdata[actual_frames:].fill(0)

            self.current_frame += actual_frames

    def play(self):
        """Start or resume playback."""
        with self._lock:
            if not self.tracks or self.total_frames == 0:
                return

            if self.current_frame >= self.total_frames:
                self.current_frame = 0

            self.is_playing = True

            if self.stream is None or not self.stream.active:
                try:
                    self.stream = sd.OutputStream(
                        samplerate=self.sample_rate,
                        channels=2,
                        dtype='float32',
                        callback=self._audio_callback,
                        blocksize=2048
                    )
                    self.stream.start()
                except Exception as e:
                    self.is_playing = False
                    raise RuntimeError(f"Erro ao inicializar dispositivo de áudio: {e}")

        self._start_position_monitor()

    def pause(self):
        """Pause playback without resetting position."""
        with self._lock:
            self.is_playing = False

    def stop(self):
        """Stop playback and rewind to beginning without deadlocks."""
        stream_to_close = None
        with self._lock:
            self.is_playing = False
            self.current_frame = 0
            stream_to_close = self.stream
            self.stream = None
                
        if stream_to_close is not None:
            try:
                stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                pass

        self._stop_position_monitor()
        if self.on_position_update:
            self.on_position_update(0.0, self.duration_seconds)

    def is_stem_audible(self, stem_name: str) -> bool:
        """Return True if stem is currently audible (considering solo/mute/volume)."""
        with self._lock:
            if stem_name not in self.tracks:
                return False
            track = self.tracks[stem_name]
            solo_tracks = [t for t in self.tracks.values() if t.is_solo]
            if solo_tracks and not track.is_solo:
                return False
            if not solo_tracks and track.is_muted:
                return False
            return track.volume > 0.001 and self.master_volume > 0.001

    def close(self):
        """Explicit cleanup."""
        self.stop()

    def _start_position_monitor(self):
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _stop_position_monitor(self):
        self._monitor_running = False

    def _monitor_loop(self):
        while self._monitor_running and self.is_playing:
            if self.on_position_update:
                self.on_position_update(self.current_time_seconds, self.duration_seconds)
            time.sleep(0.05)
