"""
State Manager for TUI
Uses watchdog for filesystem event notifications instead of polling
"""
import json
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
from threading import Lock
import asyncio

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from .models import (
    LauncherState, RunState, Checkpoint, CompletedRunSummary,
    QuestionResult, GridItem, RunStatus
)


class StateFileHandler(FileSystemEventHandler):
    """Handle filesystem events for state files"""
    
    def __init__(self, manager: 'StateManager'):
        self.manager = manager
        self._lock = Lock()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        with self._lock:
            self._handle_file_change(event.src_path)
    
    def on_created(self, event):
        if event.is_directory:
            return
        with self._lock:
            self._handle_file_change(event.src_path)
    
    def _handle_file_change(self, filepath: str):
        """Handle a file change event"""
        filename = os.path.basename(filepath)
        
        if filename == "launcher_state.json":
            self.manager._on_launcher_state_changed()
        elif filename == "run_state.json":
            self.manager._on_run_state_changed()
        elif filename == "checkpoint.json":
            self.manager._on_checkpoint_changed()
        elif filename.endswith(".json") and "results" in filepath:
            self.manager._on_results_changed()


class StateManager:
    """
    Manages state files and notifies callbacks on changes.
    Uses watchdog for efficient filesystem monitoring (no polling).
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
        
        # State cache
        self._launcher_state: Optional[LauncherState] = None
        self._run_state: Optional[RunState] = None
        self._checkpoint: Optional[Checkpoint] = None
        self._completed_runs: List[CompletedRunSummary] = []
        
        # Dataset difficulties cache: question_id -> difficulty
        self._dataset_difficulties: Dict[str, str] = {}
        self._load_dataset_difficulties()
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "launcher_state": [],
            "run_state": [],
            "checkpoint": [],
            "results": [],
        }
        
        # File system observer
        self._observer: Optional[Observer] = None
        self._handler = StateFileHandler(self)
        
        # Polling fallback timestamps
        self._last_run_state_mtime: float = 0
        self._last_launcher_state_mtime: float = 0
        
        # Lock for thread safety
        self._lock = Lock()
        
        # Load initial state
        self._load_all_state()
        self._load_completed_runs()
    
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
    
    # ==================== Dataset Loading ====================
    
    def _load_dataset_difficulties(self) -> None:
        """Load difficulty information from dataset.jsonl"""
        self._dataset_difficulties = {}
        if not self.dataset_path.exists():
            print(f"Warning: Dataset not found at {self.dataset_path}")
            return
        
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        q_id = data.get("question_id")
                        difficulty = data.get("difficulty", "unknown")
                        if q_id:
                            self._dataset_difficulties[q_id] = difficulty
                    except json.JSONDecodeError:
                        continue
        except IOError as e:
            print(f"Error loading dataset: {e}")
    
    def get_difficulty_for_question(self, question_id: str) -> str:
        """Get difficulty for a question_id from cached dataset"""
        return self._dataset_difficulties.get(question_id, "unknown")
    
    # ==================== Observer Management ====================
    
    def start_watching(self):
        """Start watching for file changes"""
        if self._observer is not None:
            return
        
        self._observer = Observer()
        # Watch state directory
        self._observer.schedule(self._handler, str(self.state_dir), recursive=False)
        # Watch results directory
        self._observer.schedule(self._handler, str(self.results_dir), recursive=False)
        self._observer.start()
    
    def poll_for_changes(self) -> None:
        """
        Poll for file changes as fallback for watchdog.
        Call this periodically from the TUI (e.g., every 0.5s).
        Only triggers callbacks if file actually changed.
        """
        # Check run_state.json
        try:
            if self.run_state_path.exists():
                mtime = self.run_state_path.stat().st_mtime
                if mtime > self._last_run_state_mtime:
                    self._last_run_state_mtime = mtime
                    self._on_run_state_changed()
        except Exception:
            pass
        
        # Check launcher_state.json
        try:
            if self.launcher_state_path.exists():
                mtime = self.launcher_state_path.stat().st_mtime
                if mtime > self._last_launcher_state_mtime:
                    self._last_launcher_state_mtime = mtime
                    self._on_launcher_state_changed()
        except Exception:
            pass
    
    def stop_watching(self):
        """Stop watching for file changes"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    # ==================== Callbacks ====================
    
    def on_launcher_state_change(self, callback: Callable[[LauncherState], None]):
        """Register callback for launcher state changes"""
        self._callbacks["launcher_state"].append(callback)
    
    def on_run_state_change(self, callback: Callable[[RunState], None]):
        """Register callback for run state changes"""
        self._callbacks["run_state"].append(callback)
    
    def on_checkpoint_change(self, callback: Callable[[Checkpoint], None]):
        """Register callback for checkpoint changes"""
        self._callbacks["checkpoint"].append(callback)
    
    def on_results_change(self, callback: Callable[[List[CompletedRunSummary]], None]):
        """Register callback for results changes"""
        self._callbacks["results"].append(callback)
    
    def _notify(self, event_type: str, data: Any):
        """Notify all callbacks for an event type"""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Error in callback for {event_type}: {e}")
    
    # ==================== Event Handlers ====================
    
    def _on_launcher_state_changed(self):
        """Handle launcher state file change"""
        state = self._read_json(self.launcher_state_path)
        if state:
            with self._lock:
                self._launcher_state = LauncherState(**state)
            self._notify("launcher_state", self._launcher_state)
    
    def _on_run_state_changed(self):
        """Handle run state file change"""
        state = self._read_json(self.run_state_path)
        if state:
            with self._lock:
                self._run_state = RunState(**state)
            self._notify("run_state", self._run_state)
    
    def _on_checkpoint_changed(self):
        """Handle checkpoint file change"""
        state = self._read_json(self.checkpoint_path)
        if state:
            with self._lock:
                self._checkpoint = Checkpoint(**state)
            self._notify("checkpoint", self._checkpoint)
    
    def _on_results_changed(self):
        """Handle results directory change"""
        self._load_completed_runs()
        self._notify("results", self._completed_runs)
    
    # ==================== State Loading ====================
    
    def _read_json(self, path: Path) -> Optional[Dict]:
        """Read and parse a JSON file"""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading {path}: {e}")
        return None
    
    def _write_json(self, path: Path, data: Dict):
        """Write data to a JSON file"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except IOError as e:
            print(f"Error writing {path}: {e}")
    
    def _load_all_state(self):
        """Load all state files"""
        self._on_launcher_state_changed()
        self._on_run_state_changed()
        self._on_checkpoint_changed()
    
    def _load_completed_runs(self):
        """Load completed runs from results directory"""
        completed = []
        
        for result_file in self.results_dir.glob("*.json"):
            try:
                data = self._read_json(result_file)
                if data:
                    results = data.get("results", [])
                    
                    # Calcular estatísticas por dificuldade (usa dataset lookup)
                    difficulty_stats = self._calculate_difficulty_stats(results)
                    
                    # Calculate score from difficulty stats
                    easy_pct = difficulty_stats["easy"]["percentage"]
                    medium_pct = difficulty_stats["medium"]["percentage"]
                    hard_pct = difficulty_stats["hard"]["percentage"]
                    score = (easy_pct * 1 + medium_pct * 3 + hard_pct * 5) / 9
                    
                    # Calculate total tokens
                    total_in = sum(r.get("total_input_tokens", 0) for r in results)
                    total_out = sum(r.get("total_output_tokens", 0) for r in results)
                    
                    # Tempo total
                    total_time = data.get("total_test_time", 0.0)
                    
                    # Tokens por segundo
                    tokens_per_second = data.get("tokens_per_second", 0.0)
                    if tokens_per_second == 0.0 and total_time > 0:
                        tokens_per_second = total_out / total_time
                    
                    # Extrair estatísticas
                    easy_stats = difficulty_stats.get("easy", {})
                    medium_stats = difficulty_stats.get("medium", {})
                    hard_stats = difficulty_stats.get("hard", {})
                    total_stats = difficulty_stats.get("total", {})
                    
                    summary = CompletedRunSummary(
                        model=data.get("model", "unknown"),
                        architecture=data.get("architecture", "unknown"),
                        total_input_tokens=total_in,
                        total_output_tokens=total_out,
                        score=score,
                        total_questions=len(results),
                        result_file=str(result_file),
                        total_time=total_time,
                        tokens_per_second=tokens_per_second,
                        easy_percentage=easy_stats.get("percentage", 0.0),
                        medium_percentage=medium_stats.get("percentage", 0.0),
                        hard_percentage=hard_stats.get("percentage", 0.0),
                        total_percentage=total_stats.get("percentage", 0.0),
                        easy_total=easy_stats.get("total", 0),
                        easy_passed=easy_stats.get("passed", 0),
                        medium_total=medium_stats.get("total", 0),
                        medium_passed=medium_stats.get("passed", 0),
                        hard_total=hard_stats.get("total", 0),
                        hard_passed=hard_stats.get("passed", 0),
                        total_passed=total_stats.get("passed", 0),
                    )
                    completed.append(summary)
            except Exception as e:
                print(f"Error loading result {result_file}: {e}")
        
        with self._lock:
            self._completed_runs = completed
    
    def _calculate_difficulty_stats(self, results: List[Dict]) -> Dict[str, Dict]:
        """Calcula estatísticas por dificuldade a partir dos resultados usando dataset"""
        stats = {
            "easy": {"total": 0, "success_sum": 0.0, "percentage": 0.0},
            "medium": {"total": 0, "success_sum": 0.0, "percentage": 0.0},
            "hard": {"total": 0, "success_sum": 0.0, "percentage": 0.0},
            "total": {"total": 0, "success_sum": 0.0, "percentage": 0.0},
        }
        
        for result in results:
            question_id = result.get("question_id", "")
            # Lookup difficulty from dataset
            difficulty = self.get_difficulty_for_question(question_id)
            if difficulty not in ["easy", "medium", "hard"]:
                difficulty = "medium"  # Default if unknown
            
            success_rate = result.get("success_rate", 0.0)
            
            stats[difficulty]["total"] += 1
            stats[difficulty]["success_sum"] += success_rate
            stats["total"]["total"] += 1
            stats["total"]["success_sum"] += success_rate
        
        # Calculate percentages (average success_rate per difficulty)
        for diff in ["easy", "medium", "hard", "total"]:
            total = stats[diff]["total"]
            success_sum = stats[diff]["success_sum"]
            # Percentage = average success_rate * 100
            stats[diff]["percentage"] = (success_sum / total * 100) if total > 0 else 0.0
            # Keep passed count for compatibility (rounded)
            stats[diff]["passed"] = int(success_sum) if success_sum == int(success_sum) else round(success_sum, 2)
        
        return stats
    
    def _calculate_score_from_results(self, results: List[Dict]) -> float:
        """
        Calculate weighted score from results list.
        Score = ((%_easy * 1) + (%_medium * 3) + (%_hard * 5)) / 9
        """
        if not results:
            return 0.0
        
        # Get difficulty stats first
        difficulty_stats = self._calculate_difficulty_stats(results)
        
        easy_pct = difficulty_stats["easy"]["percentage"]
        medium_pct = difficulty_stats["medium"]["percentage"]
        hard_pct = difficulty_stats["hard"]["percentage"]
        
        # Score formula: weighted average
        score = (easy_pct * 1 + medium_pct * 3 + hard_pct * 5) / 9
        
        return score
    
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
        with self._lock:
            return self._completed_runs.copy()
    
    # ==================== State Writing (for main.py and launcher) ====================
    
    def save_launcher_state(self, state: LauncherState):
        """Save launcher state to file"""
        self._write_json(self.launcher_state_path, state.model_dump())
    
    def save_run_state(self, state: RunState):
        """Save run state to file"""
        self._write_json(self.run_state_path, state.model_dump())
    
    def save_checkpoint(self, checkpoint: Checkpoint):
        """Save checkpoint to file"""
        self._write_json(self.checkpoint_path, checkpoint.model_dump())
    
    def clear_run_state(self):
        """Clear the run state file"""
        if self.run_state_path.exists():
            self.run_state_path.unlink()
        with self._lock:
            self._run_state = None
    
    # ==================== Checkpoint Management ====================
    
    def has_checkpoint(self) -> bool:
        """Check if there's a valid checkpoint to resume from"""
        return self.checkpoint_path.exists() and self._checkpoint is not None
    
    def clear_checkpoint(self):
        """Clear the checkpoint file"""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
        with self._lock:
            self._checkpoint = None
