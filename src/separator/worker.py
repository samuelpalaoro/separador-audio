"""Background QThread worker for non-blocking audio separation."""
from PySide6.QtCore import QThread, Signal
from src.separator.demucs_engine import DemucsEngine, CancellationRequestedError


class SeparationWorker(QThread):
    """Worker thread that executes audio separation without freezing the GUI."""
    
    # Signals
    sig_progress = Signal(int, str)
    sig_finished = Signal(object, int, object)  # stems_dict, sample_rate, metadata
    sig_error = Signal(str)
    sig_cancelled = Signal()

    def __init__(
        self,
        filepath: str,
        model_name: str = "htdemucs",
        device_name: str = None,
        shifts: int = 1,
        overlap: float = 0.25,
        parent=None
    ):
        super().__init__(parent)
        self.filepath = filepath
        self.model_name = model_name
        self.device_name = device_name
        self.shifts = shifts
        self.overlap = overlap
        self._is_cancelled = False
        self.engine = DemucsEngine()

    def cancel(self):
        """Signal the worker to abort processing."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        """Thread execution."""
        try:
            stems, sample_rate, meta = self.engine.separate(
                filepath=self.filepath,
                model_name=self.model_name,
                device_name=self.device_name,
                shifts=self.shifts,
                overlap=self.overlap,
                progress_callback=self._on_progress,
                cancel_check=self.is_cancelled
            )

            if self._is_cancelled:
                self.sig_cancelled.emit()
            else:
                self.sig_finished.emit(stems, sample_rate, meta)

        except CancellationRequestedError:
            self.sig_cancelled.emit()
        except MemoryError:
            self.sig_error.emit(
                "Memória insuficiente (RAM ou VRAM) para processar este arquivo com o modelo selecionado.\n"
                "Dica: Feche outros programas em segundo plano ou tente um modelo mais leve."
            )
        except Exception as e:
            self.sig_error.emit(f"Falha durante o processamento do áudio: {str(e)}")

    def _on_progress(self, percent: int, message: str):
        if not self._is_cancelled:
            self.sig_progress.emit(percent, message)
