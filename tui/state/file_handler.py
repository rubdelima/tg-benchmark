"""
File system event handler for state files.
Uses watchdog for filesystem event notifications.
"""
import os
from threading import Lock
from watchdog.events import FileSystemEventHandler


class StateFileHandler(FileSystemEventHandler):
    """
    Handle filesystem events for state files.
    
    Monitora mudanças em arquivos de estado e notifica o StateManager.
    """
    
    def __init__(self, manager: 'StateManager'):
        self.manager = manager
        self._lock = Lock()
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        with self._lock:
            self._handle_file_change(event.src_path)
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
        with self._lock:
            self._handle_file_change(event.src_path)
    
    def _handle_file_change(self, filepath: str):
        """
        Route file change to appropriate handler.
        
        Args:
            filepath: Path to the changed file
        """
        filename = os.path.basename(filepath)
        
        if filename == "launcher_state.json":
            self.manager._on_launcher_state_changed()
        elif filename == "run_state.json":
            self.manager._on_run_state_changed()
        elif filename == "checkpoint.json":
            self.manager._on_checkpoint_changed()
        elif filename.endswith(".json") and "results" in filepath:
            self.manager._on_results_changed()
