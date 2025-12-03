"""
Event handlers for BenchmarkTUI application.
Separado do app.py para melhor organização.
"""
import threading
from typing import Optional, TYPE_CHECKING

from .state import LauncherState, RunState, CompletedRunSummary
from .widgets import CurrentRunWidget, ResultsTableWidget, ProgressBarsWidget, HistoryTableWidget
from .config import get_benchmark_grid, get_expected_questions

if TYPE_CHECKING:
    from .app import BenchmarkTUI


class TUIEventHandlers:
    """
    Handlers de eventos para a TUI.
    
    Gerencia callbacks do StateManager e atualização de widgets.
    """
    
    def __init__(self, app: 'BenchmarkTUI'):
        self.app = app
        self._thread_id: Optional[int] = None
    
    def setup(self):
        """Configura handlers e inicia observação"""
        self._thread_id = threading.get_ident()
        
        # Registrar callbacks
        sm = self.app.state_manager
        sm.on_launcher_state_change(self._on_launcher_state_change)
        sm.on_run_state_change(self._on_run_state_change)
        sm.on_results_change(self._on_results_change)
        
        # Iniciar observação
        sm.start_watching()
        
        # Carregar dados iniciais
        self._load_initial_data()
    
    def teardown(self):
        """Para observação"""
        self.app.state_manager.stop_watching()
    
    def poll(self):
        """Polling fallback para Windows"""
        try:
            self.app.state_manager.poll_for_changes()
        except Exception:
            pass
    
    def refresh(self):
        """Recarrega todos os dados"""
        self._load_initial_data()
    
    def update_time_display(self):
        """Atualiza display de tempo (chamado periodicamente)"""
        try:
            run_state = self.app.state_manager.run_state
            if run_state:
                widget = self.app.query_one("#current-run", CurrentRunWidget)
                widget.update_from_state(run_state)
        except Exception:
            pass
    
    # ==================== Private Methods ====================
    
    def _load_initial_data(self):
        """Carrega dados iniciais"""
        # Carregar resultados existentes
        results = self.app.state_manager.completed_runs
        if results:
            try:
                widget = self.app.query_one("#results-table", ResultsTableWidget)
                widget.update_from_results(results)
            except Exception:
                pass
        
        # Calcular progresso
        self._calculate_launcher_progress()
        
        # Carregar estados
        sm = self.app.state_manager
        if sm.launcher_state:
            self._on_launcher_state_change(sm.launcher_state)
        if sm.run_state:
            self._on_run_state_change(sm.run_state)
    
    def _calculate_launcher_progress(self):
        """Calcula progresso baseado em questões concluídas"""
        try:
            config = self.app.config
            
            # Calcula total de runs e questões
            grid = get_benchmark_grid(config)
            total_runs = len(grid)
            expected_questions = get_expected_questions(config)
            total_questions = total_runs * expected_questions
            
            # Conta questões concluídas
            total_completed = 0
            for run in self.app.state_manager.completed_runs:
                if hasattr(run, 'easy_total') and hasattr(run, 'medium_total'):
                    total_completed += run.easy_total + run.medium_total + run.hard_total
                elif hasattr(run, 'total_questions'):
                    total_completed += run.total_questions
            
            # Atualiza widget
            widget = self.app.query_one("#progress-bars", ProgressBarsWidget)
            widget.update_launcher_progress(total_completed, total_questions)
        except Exception:
            pass
    
    def _on_launcher_state_change(self, state: LauncherState):
        """Handler para mudanças no estado do launcher"""
        if self._is_main_thread():
            self._update_launcher_state(state)
        else:
            self.app.call_from_thread(self._update_launcher_state, state)
    
    def _update_launcher_state(self, state: LauncherState):
        """Atualiza UI do estado do launcher"""
        try:
            widget = self.app.query_one("#progress-bars", ProgressBarsWidget)
            widget.update_launcher_progress(state.completed_runs, state.total_runs)
        except Exception:
            pass
    
    def _on_run_state_change(self, state: RunState):
        """Handler para mudanças no estado da execução"""
        if self._is_main_thread():
            self._update_run_state(state)
        else:
            self.app.call_from_thread(self._update_run_state, state)
    
    def _update_run_state(self, state: RunState):
        """Atualiza UI do estado da execução"""
        try:
            current_run = self.app.query_one("#current-run", CurrentRunWidget)
            current_run.update_from_state(state)
            
            progress = self.app.query_one("#progress-bars", ProgressBarsWidget)
            progress.update_run_progress(state.completed_questions, state.total_questions)
        except Exception:
            pass
    
    def _on_results_change(self, results: list):
        """Handler para mudanças nos resultados"""
        if self._is_main_thread():
            self._update_results(results)
        else:
            self.app.call_from_thread(self._update_results, results)
    
    def _update_results(self, results: list):
        """Atualiza UI dos resultados"""
        try:
            widget = self.app.query_one("#results-table", ResultsTableWidget)
            widget.update_from_results(results)
            
            # Recalcula progresso total quando resultados mudam
            self._calculate_launcher_progress()
        except Exception:
            pass
    
    def _is_main_thread(self) -> bool:
        """Verifica se está na thread principal"""
        return self._thread_id and threading.get_ident() == self._thread_id
