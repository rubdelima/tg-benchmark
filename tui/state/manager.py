"""
State Manager for TUI - Coordena observação de arquivos e callbacks.

Este módulo é o ponto central de gerenciamento de estado da TUI.
Usa watchdog para monitoramento de arquivos e notifica widgets via callbacks.
"""
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from threading import Lock

from watchdog.observers import Observer

from .models import LauncherState, RunState, Checkpoint, CompletedRunSummary
from .file_handler import StateFileHandler
from .results_loader import ResultsLoader
from .poller import StatePoller
from ..data import DatasetLoader, load_results_file, save_json_file


class StateManager:
    """
    Gerencia arquivos de estado e notifica callbacks em mudanças.
    
    Responsabilidades:
    - Observar mudanças em arquivos de estado (.tui_state/)
    - Observar novos resultados (results/)
    - Notificar widgets via sistema de callbacks
    - Prover acesso thread-safe ao estado atual
    """
    
    STATE_DIR = ".tui_state"
    LAUNCHER_STATE_FILE = "launcher_state.json"
    RUN_STATE_FILE = "run_state.json"
    CHECKPOINT_FILE = "checkpoint.json"
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.state_dir = self.base_path / self.STATE_DIR
        self.results_dir = self.base_path / "results"
        self.dataset_path = self.base_path / "data" / "dataset.jsonl"
        
        # Ensure directories exist
        self.state_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        
        # Dataset loader (singleton)
        self._dataset_loader = DatasetLoader(self.dataset_path)
        
        # Results loader
        self._results_loader = ResultsLoader(self.results_dir, self._dataset_loader)
        
        # State cache
        self._launcher_state: Optional[LauncherState] = None
        self._run_state: Optional[RunState] = None
        self._checkpoint: Optional[Checkpoint] = None
        
        # Callbacks registry
        self._callbacks: Dict[str, List[Callable]] = {
            "launcher_state": [], "run_state": [], "checkpoint": [], "results": [],
        }
        
        # File system observer and poller
        self._observer: Optional[Observer] = None
        self._handler = StateFileHandler(self)
        self._poller = StatePoller(
            self.state_dir, self.results_dir,
            self.RUN_STATE_FILE, self.LAUNCHER_STATE_FILE
        )
        
        # Lock for thread safety
        self._lock = Lock()
        
        # Load initial state
        self._load_all_state()
        self._results_loader.load_all()
    
    # ==================== File Paths ====================
    
    @property
    def launcher_state_path(self) -> Path:
        return self.state_dir / self.LAUNCHER_STATE_FILE
    
    @property
    def run_state_path(self) -> Path:
        return self.state_dir / self.RUN_STATE_FILE
    
    @property
    def checkpoint_path(self) -> Path:
        return self.state_dir / self.CHECKPOINT_FILE
    
    # ==================== Dataset Access ====================
    
    def get_difficulty_for_question(self, question_id: str) -> str:
        return self._dataset_loader.get_difficulty(question_id)
    
    # ==================== Observer Management ====================
    
    def start_watching(self):
        if self._observer is not None:
            return
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.state_dir), recursive=False)
        self._observer.schedule(self._handler, str(self.results_dir), recursive=False)
        self._observer.start()
    
    def stop_watching(self):
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def poll_for_changes(self) -> None:
        """Polling fallback para Windows onde watchdog pode falhar."""
        self._poller.poll_state_files(
            self._on_run_state_changed,
            self._on_launcher_state_changed
        )
        self._poller.poll_results_files(self._on_results_changed)
    
    # ==================== Callbacks ====================
    
    def on_launcher_state_change(self, callback: Callable[[LauncherState], None]):
        self._callbacks["launcher_state"].append(callback)
    
    def on_run_state_change(self, callback: Callable[[RunState], None]):
        self._callbacks["run_state"].append(callback)
    
    def on_checkpoint_change(self, callback: Callable[[Checkpoint], None]):
        self._callbacks["checkpoint"].append(callback)
    
    def on_results_change(self, callback: Callable[[List[CompletedRunSummary]], None]):
        self._callbacks["results"].append(callback)
    
    def _notify(self, event_type: str, data: Any):
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception:
                pass
    
    # ==================== Event Handlers ====================
    
    def _on_launcher_state_changed(self):
        data = load_results_file(self.launcher_state_path)
        if data:
            with self._lock:
                self._launcher_state = LauncherState(**data)
            self._notify("launcher_state", self._launcher_state)
    
    def _on_run_state_changed(self):
        data = load_results_file(self.run_state_path)
        if data:
            with self._lock:
                self._run_state = RunState(**data)
            self._notify("run_state", self._run_state)
    
    def _on_checkpoint_changed(self):
        data = load_results_file(self.checkpoint_path)
        if data:
            with self._lock:
                self._checkpoint = Checkpoint(**data)
            self._notify("checkpoint", self._checkpoint)
    
    def _on_results_changed(self):
        self._results_loader.load_all()
        self._notify("results", self._results_loader.completed_runs)
    
    def _load_all_state(self):
        self._on_launcher_state_changed()
        self._on_run_state_changed()
        self._on_checkpoint_changed()
    
    # ==================== Public Getters ====================
    
    @property
    def launcher_state(self) -> Optional[LauncherState]:
        with self._lock:
            return self._launcher_state
    
    @property
    def run_state(self) -> Optional[RunState]:
        with self._lock:
            return self._run_state
    
    @property
    def checkpoint(self) -> Optional[Checkpoint]:
        with self._lock:
            return self._checkpoint
    
    @property
    def completed_runs(self) -> List[CompletedRunSummary]:
        return self._results_loader.completed_runs
    
    # ==================== State Writing ====================
    
    def save_launcher_state(self, state: LauncherState):
        save_json_file(self.launcher_state_path, state.model_dump())
    
    def save_run_state(self, state: RunState):
        save_json_file(self.run_state_path, state.model_dump())
    
    def save_checkpoint(self, checkpoint: Checkpoint):
        save_json_file(self.checkpoint_path, checkpoint.model_dump())
    
    def clear_run_state(self):
        if self.run_state_path.exists():
            self.run_state_path.unlink()
        with self._lock:
            self._run_state = None
    
    # ==================== Checkpoint Management ====================
    
    def has_checkpoint(self) -> bool:
        return self.checkpoint_path.exists() and self._checkpoint is not None
    
    def clear_checkpoint(self):
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
        with self._lock:
            self._checkpoint = None
