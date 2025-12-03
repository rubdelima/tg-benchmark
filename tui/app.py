"""
TG-Benchmark TUI Application
Interface de terminal para monitoramento de benchmarks.

Esta TUI é READ-ONLY: apenas monitora arquivos de estado escritos pelo benchmark.
Para executar o benchmark: python main.py
Para visualizar: python -m tui.app
"""
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer
from textual.binding import Binding

from .widgets import CurrentRunWidget, ResultsTableWidget, ProgressBarsWidget, HistoryTableWidget
from .state import StateManager
from .config import load_config, get_paths
from .handlers import TUIEventHandlers


class BenchmarkTUI(App):
    """
    TG-Benchmark Terminal User Interface (Read-Only Monitor)
    
    Esta aplicação APENAS monitora o estado do benchmark.
    Ela NÃO executa o benchmark - para isso use: python main.py
    """
    
    TITLE = "🧪 TG-Benchmark TUI"
    SUB_TITLE = "Monitor de Benchmark (Read-Only)"
    
    CSS = """
    Screen { layout: vertical; }
    #main-container { height: 1fr; width: 100%; }
    #bottom-panel { width: 100%; height: auto; dock: bottom; }
    #progress-bars { width: 100%; height: auto; }
    CurrentRunWidget { height: auto; }
    ResultsTableWidget { height: 100%; }
    #history-container { display: none; width: 100%; height: 1fr; }
    #history-container.visible { display: block; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("r", "refresh", "Refresh"),
        Binding("h", "toggle_history", "Histórico"),
    ]
    
    def __init__(self, base_path: str = ".", config_path: str = "config.yaml"):
        super().__init__()
        self.base_path = Path(base_path)
        self.config_path = config_path
        self.config = load_config(config_path)
        self.state_manager = StateManager(str(base_path))
        self._handlers = TUIEventHandlers(self)
        self._history_visible = False
    
    def compose(self) -> ComposeResult:
        """Monta a estrutura visual da aplicação"""
        yield Header()
        
        # Main view - tabela de resultados
        with Vertical(id="main-container"):
            yield ResultsTableWidget(id="results-table")
        
        # History view (oculto por padrão)
        paths = get_paths(self.config)
        with Vertical(id="history-container"):
            yield HistoryTableWidget(
                id="history-table",
                results_dir=paths["results_dir"],
                dataset_path=paths["dataset_file"]
            )
        
        # Bottom panel: execução atual + barras de progresso
        with Vertical(id="bottom-panel"):
            yield CurrentRunWidget(id="current-run")
            yield ProgressBarsWidget(id="progress-bars")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Inicializa a aplicação"""
        self._handlers.setup()
        self.set_interval(1.0, self._handlers.update_time_display)
        self.set_interval(0.5, self._handlers.poll)
    
    def on_unmount(self) -> None:
        """Finaliza a aplicação"""
        self._handlers.teardown()
    
    # ==================== Actions ====================
    
    def action_quit(self) -> None:
        """Sair da aplicação"""
        self.exit()
    
    def action_refresh(self) -> None:
        """Atualizar dados"""
        self._handlers.refresh()
        self.notify("Dados atualizados", severity="information")
    
    def action_toggle_history(self) -> None:
        """Alternar visão de histórico"""
        self._history_visible = not self._history_visible
        
        main = self.query_one("#main-container")
        history = self.query_one("#history-container")
        
        if self._history_visible:
            main.display = False
            history.add_class("visible")
            history.display = True
            try:
                self.query_one("#history-table", HistoryTableWidget).refresh_data()
            except Exception:
                pass
            self.notify("Histórico (H para fechar)", severity="information")
        else:
            main.display = True
            history.remove_class("visible")
            history.display = False


def run_tui(base_path: str = ".", config_path: str = "config.yaml"):
    """Função de entrada para executar a TUI"""
    app = BenchmarkTUI(base_path=base_path, config_path=config_path)
    app.run()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TG-Benchmark TUI Monitor")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--base-path", type=str, default=".")
    
    args = parser.parse_args()
    run_tui(base_path=args.base_path, config_path=args.config)


if __name__ == "__main__":
    main()
