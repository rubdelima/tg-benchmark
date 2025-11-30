"""
TG-Benchmark TUI Application
Interface de terminal para monitoramento de benchmarks.

Esta TUI é READ-ONLY: apenas monitora arquivos de estado escritos pelo benchmark.
Para executar o benchmark: python main.py
Para visualizar: python -m tui.app
"""
import threading
from pathlib import Path
from typing import Optional, Dict, Any

import yaml
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer
from textual.binding import Binding

from .widgets import CurrentRunWidget, ResultsTableWidget, ProgressBarsWidget, HistoryTableWidget
from .state import StateManager, LauncherState, RunState


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Carrega configuração do arquivo YAML."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


class BenchmarkTUI(App):
    """
    TG-Benchmark Terminal User Interface (Read-Only Monitor)
    
    Esta aplicação APENAS monitora o estado do benchmark.
    Ela NÃO executa o benchmark - para isso use: python main.py
    
    Layout:
    ┌───────────────────────────────────────────────────────────────────────┐
    │                    🧪 TG-Benchmark TUI                                │
    ├──────────────────────────────────┬────────────────────────────────────┤
    │  📊 Execução Atual               │  📈 Resultados Concluídos          │
    │  ─────────────────               │  ────────────────                  │
    │  🤖 Modelo: qwen3:8b             │  ┌──────────────────────────────┐  │
    │  🏗️  Arquitetura: multi-agent     │  │ Model│Arch│Score│Easy│...   │  │
    │  📝 Questão: abc301_a (15/100)   │  ├──────┼────┼─────┼────┼─────┤  │
    │  ⏱️  Tempo Total: 02:25:37        │  │ ...  │... │...  │... │...  │  │
    │  💾 Tokens: In: 4.2M | Out: 3.4M │  └──────────────────────────────┘  │
    │  ✅ Score Atual: 70%              │                                    │
    ├──────────────────────────────────┴────────────────────────────────────┤
    │ 📦 Progresso Total: [████████░░░░░░░] 5/18 (27.8%)                    │
    │ 📝 Questões: [██████████░░░░] 15/100 (15.0%)                          │
    ├───────────────────────────────────────────────────────────────────────┤
    │ q: Sair | r: Refresh | h: Histórico                                  │
    └───────────────────────────────────────────────────────────────────────┘
    """
    
    TITLE = "🧪 TG-Benchmark TUI"
    SUB_TITLE = "Monitor de Benchmark (Read-Only)"
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #main-container {
        height: 1fr;
        width: 100%;
    }
    
    #bottom-panel {
        width: 100%;
        height: auto;
        dock: bottom;
    }
    
    #progress-bars {
        width: 100%;
        height: auto;
    }
    
    CurrentRunWidget {
        height: auto;
    }
    
    ResultsTableWidget {
        height: 100%;
    }
    
    /* History view */
    #history-container {
        display: none;
        width: 100%;
        height: 1fr;
    }
    
    #history-container.visible {
        display: block;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("r", "refresh", "Refresh"),
        Binding("h", "toggle_history", "Histórico"),
    ]
    
    def __init__(
        self,
        base_path: str = ".",
        config_path: str = "config.yaml",
    ):
        super().__init__()
        self.base_path = Path(base_path)
        self.config_path = config_path
        self.state_manager = StateManager(str(base_path))
        self._history_visible = False
        self._thread_id: Optional[int] = None
        
        # Carregar configuração
        self.config = load_config(config_path)
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # Main view - results table takes full width
        with Vertical(id="main-container"):
            yield ResultsTableWidget(id="results-table")
        
        # History view (hidden by default)
        results_dir = self.config.get("paths", {}).get("results", "./results/")
        dataset_file = self.config.get("paths", {}).get("dataset_file", "./data/dataset.jsonl")
        with Vertical(id="history-container"):
            yield HistoryTableWidget(
                id="history-table",
                results_dir=results_dir,
                dataset_path=dataset_file
            )
        
        # Bottom panel: Current Run + Progress Bars
        with Vertical(id="bottom-panel"):
            yield CurrentRunWidget(id="current-run")
            yield ProgressBarsWidget(id="progress-bars")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Chamado quando o app é montado"""
        # Salvar ID da thread principal para detectar chamadas cross-thread
        self._thread_id = threading.get_ident()
        
        # Registrar callbacks para mudanças de estado
        self.state_manager.on_launcher_state_change(self._on_launcher_state_change)
        self.state_manager.on_run_state_change(self._on_run_state_change)
        self.state_manager.on_results_change(self._on_results_change)
        
        # Iniciar observação de arquivos
        self.state_manager.start_watching()
        
        # Carregar dados iniciais
        self._load_initial_data()
        
        # Atualização periódica do tempo
        self.set_interval(1.0, self._update_time_display)
        
        # Polling fallback para mudanças de arquivo (Windows)
        self.set_interval(0.5, self._poll_state_changes)
    
    def on_unmount(self) -> None:
        """Chamado quando o app é desmontado"""
        self.state_manager.stop_watching()
    
    def _load_initial_data(self) -> None:
        """Carrega dados iniciais dos arquivos de estado e resultados"""
        # Carregar resultados existentes
        results = self.state_manager.completed_runs
        if results:
            try:
                results_widget = self.query_one("#results-table", ResultsTableWidget)
                results_widget.update_from_results(results)
            except Exception:
                pass
        
        # Calcular progresso do launcher com base no config e resultados existentes
        self._calculate_launcher_progress()
        
        # Carregar estado atual se existir
        if self.state_manager.launcher_state:
            self._on_launcher_state_change(self.state_manager.launcher_state)
        
        if self.state_manager.run_state:
            self._on_run_state_change(self.state_manager.run_state)
    
    def _calculate_launcher_progress(self) -> None:
        """Calcula progresso do launcher baseado em config e resultados existentes"""
        try:
            models_config = self.config.get("benchmark", {}).get("models", {})
            total_models = sum(len(params) for params in models_config.values())
            
            architectures = self.config.get("benchmark", {}).get("architectures", ["simple"])
            test_all = self.config.get("benchmark", {}).get("test_all_combinations", True)
            
            if test_all:
                total_runs = total_models * len(architectures)
            else:
                total_runs = total_models
            
            completed_runs = len(self.state_manager.completed_runs)
            
            progress_widget = self.query_one("#progress-bars", ProgressBarsWidget)
            progress_widget.update_launcher_progress(completed_runs, total_runs)
        except Exception:
            pass
    
    def _on_launcher_state_change(self, state: LauncherState) -> None:
        """Handler para mudanças no estado do launcher"""
        if self._thread_id and threading.get_ident() == self._thread_id:
            self._update_launcher_state(state)
        else:
            self.call_from_thread(self._update_launcher_state, state)
    
    def _update_launcher_state(self, state: LauncherState) -> None:
        """Atualiza UI do estado do launcher"""
        try:
            progress_widget = self.query_one("#progress-bars", ProgressBarsWidget)
            progress_widget.update_launcher_progress(
                state.completed_runs,
                state.total_runs
            )
        except Exception:
            pass
    
    def _on_run_state_change(self, state: RunState) -> None:
        """Handler para mudanças no estado da execução"""
        if self._thread_id and threading.get_ident() == self._thread_id:
            self._update_run_state(state)
        else:
            self.call_from_thread(self._update_run_state, state)
    
    def _update_run_state(self, state: RunState) -> None:
        """Atualiza UI do estado da execução"""
        try:
            current_run = self.query_one("#current-run", CurrentRunWidget)
            current_run.update_from_state(state)
            
            progress_widget = self.query_one("#progress-bars", ProgressBarsWidget)
            progress_widget.update_run_progress(
                state.completed_questions,
                state.total_questions
            )
        except Exception:
            pass
    
    def _on_results_change(self, results: list) -> None:
        """Handler para mudanças nos resultados"""
        if self._thread_id and threading.get_ident() == self._thread_id:
            self._update_results(results)
        else:
            self.call_from_thread(self._update_results, results)
    
    def _update_results(self, results: list) -> None:
        """Atualiza UI dos resultados"""
        try:
            results_widget = self.query_one("#results-table", ResultsTableWidget)
            results_widget.update_from_results(results)
        except Exception:
            pass
    
    def _poll_state_changes(self) -> None:
        """Polling fallback para mudanças de arquivo (Windows)"""
        try:
            self.state_manager.poll_for_changes()
        except Exception:
            pass
    
    def _update_time_display(self) -> None:
        """Atualização periódica do display de tempo"""
        try:
            run_state = self.state_manager.run_state
            if run_state:
                current_run = self.query_one("#current-run", CurrentRunWidget)
                current_run.update_from_state(run_state)
        except Exception:
            pass
    
    # ==================== Actions ====================
    
    def action_quit(self) -> None:
        """Sair da aplicação"""
        self.exit()
    
    def action_refresh(self) -> None:
        """Atualizar dados dos arquivos"""
        self._load_initial_data()
        self.notify("Dados atualizados", severity="information")
    
    def action_toggle_history(self) -> None:
        """Alternar visualização do histórico de comparação"""
        self._history_visible = not self._history_visible
        
        main_container = self.query_one("#main-container")
        history_container = self.query_one("#history-container")
        
        if self._history_visible:
            main_container.display = False
            history_container.add_class("visible")
            history_container.display = True
            # Refresh data
            try:
                history_widget = self.query_one("#history-table", HistoryTableWidget)
                history_widget.refresh_data()
            except Exception:
                pass
            self.notify("Histórico (H para fechar)", severity="information")
        else:
            main_container.display = True
            history_container.remove_class("visible")
            history_container.display = False


def run_tui(base_path: str = ".", config_path: str = "config.yaml"):
    """Função de entrada para executar a TUI"""
    app = BenchmarkTUI(base_path=base_path, config_path=config_path)
    app.run()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TG-Benchmark TUI - Monitor de Terminal (Read-Only)",
        epilog="""
Esta TUI apenas MONITORA o estado do benchmark.
Para executar o benchmark, use: python main.py

Exemplos:
  python -m tui.app                    # Inicia TUI monitor
  python -m tui.app --config my.yaml   # Usa config customizado
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Caminho para arquivo de configuração (default: config.yaml)"
    )
    
    parser.add_argument(
        "--base-path",
        type=str,
        default=".",
        help="Diretório base do projeto (default: diretório atual)"
    )
    
    args = parser.parse_args()
    
    run_tui(base_path=args.base_path, config_path=args.config)


if __name__ == "__main__":
    main()
