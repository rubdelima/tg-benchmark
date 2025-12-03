"""
Polling utilities for state files.
Fallback para Windows onde watchdog pode falhar.
"""
from pathlib import Path
from typing import Dict, Callable


class StatePoller:
    """Realiza polling de arquivos de estado e resultados."""
    
    def __init__(
        self,
        state_dir: Path,
        results_dir: Path,
        run_state_file: str,
        launcher_state_file: str,
    ):
        self.state_dir = state_dir
        self.results_dir = results_dir
        self._run_state_path = state_dir / run_state_file
        self._launcher_state_path = state_dir / launcher_state_file
        
        # Timestamps para detectar mudanças
        self._last_run_state_mtime: float = 0
        self._last_launcher_state_mtime: float = 0
        self._results_files_mtimes: Dict[str, float] = {}
    
    def poll_state_files(
        self,
        on_run_state: Callable[[], None],
        on_launcher_state: Callable[[], None],
    ) -> None:
        """Verifica mudanças em arquivos de estado."""
        # run_state.json
        try:
            if self._run_state_path.exists():
                mtime = self._run_state_path.stat().st_mtime
                if mtime > self._last_run_state_mtime:
                    self._last_run_state_mtime = mtime
                    on_run_state()
        except Exception:
            pass
        
        # launcher_state.json
        try:
            if self._launcher_state_path.exists():
                mtime = self._launcher_state_path.stat().st_mtime
                if mtime > self._last_launcher_state_mtime:
                    self._last_launcher_state_mtime = mtime
                    on_launcher_state()
        except Exception:
            pass
    
    def poll_results_files(self, on_results: Callable[[], None]) -> bool:
        """Verifica mudanças em arquivos de resultados. Retorna True se houve mudança."""
        try:
            results_changed = False
            if self.results_dir.exists():
                for json_file in self.results_dir.glob("*.json"):
                    mtime = json_file.stat().st_mtime
                    file_key = str(json_file)
                    if file_key not in self._results_files_mtimes:
                        self._results_files_mtimes[file_key] = mtime
                        results_changed = True
                    elif mtime > self._results_files_mtimes[file_key]:
                        self._results_files_mtimes[file_key] = mtime
                        results_changed = True
            
            if results_changed:
                on_results()
            return results_changed
        except Exception:
            return False
