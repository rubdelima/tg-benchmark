"""
Results Table Widget - Shows completed run results
Displays: Model, Arch, Score, Time, Easy%, Med%, Hard%, Tks/s
"""
from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from textual.reactive import reactive
from rich.text import Text
from typing import List, Optional

from ..state.models import CompletedRunSummary
from ..utils.formatters import format_tokens, get_score_color


def format_time(seconds: float) -> str:
    """Formata tempo em formato legível"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs:02d}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes:02d}m"


def format_percentage(value: float) -> str:
    """Formata porcentagem"""
    return f"{value:.0f}%"


class ResultsTableWidget(Static):
    """
    Widget displaying results of completed runs in a DataTable.
    
    Columns:
    - Model: Name of the model
    - Arch: Architecture (simple/multi-agent)
    - Score: Weighted score (%)
    - Time: Total execution time
    - Easy: Success rate for easy questions
    - Med: Success rate for medium questions
    - Hard: Success rate for hard questions
    - Tks/s: Output tokens per second
    """
    
    DEFAULT_CSS = """
    ResultsTableWidget {
        width: 100%;
        height: 100%;
        border: solid $primary;
    }
    
    ResultsTableWidget > Vertical {
        height: 100%;
    }
    
    ResultsTableWidget .section-header {
        background: $surface;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }
    
    ResultsTableWidget DataTable {
        height: 1fr;
    }
    """
    
    # Reactive property for results
    results: reactive[List[CompletedRunSummary]] = reactive(list, layout=True)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📈 Resultados Concluídos", classes="section-header")
            yield DataTable(id="results-table", zebra_stripes=True)
    
    def on_mount(self) -> None:
        """Initialize the table columns"""
        table = self.query_one("#results-table", DataTable)
        # Ordem: Model, Arch, Token Out, Time, Tks/s, Easy, Med, Hard, Total%, Score
        table.add_columns(
            "Model",
            "Arch",
            "Tok Out",
            "Time",
            "Tks/s",
            "Easy",
            "Med",
            "Hard",
            "Total%",
            "Score"
        )
        table.cursor_type = "row"
    
    def watch_results(self, results: List[CompletedRunSummary]) -> None:
        """React to results changes"""
        self._update_table(results)
    
    def _update_table(self, results: List[CompletedRunSummary]) -> None:
        """Update the table with new results"""
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()
            
            for result in results:
                # Format values
                model_text = self._truncate_model_name(result.model)
                arch_text = "simple" if result.architecture == "simple" else "multi"
                
                # Token out formatado
                tok_out_text = format_tokens(result.total_output_tokens)
                
                # Tempo total
                time_text = format_time(result.total_time)
                
                # Tokens por segundo
                tks_per_sec = f"{result.tokens_per_second:.1f}"
                
                # Porcentagens por dificuldade com cores
                easy_text = self._format_difficulty_percentage(result.easy_percentage)
                medium_text = self._format_difficulty_percentage(result.medium_percentage)
                hard_text = self._format_difficulty_percentage(result.hard_percentage)
                total_pct_text = self._format_difficulty_percentage(result.total_percentage)
                
                # Color-coded score
                score_color = get_score_color(result.score)
                score_text = Text(f"{result.score:.1f}%", style=score_color)
                
                table.add_row(
                    model_text,
                    arch_text,
                    tok_out_text,
                    time_text,
                    tks_per_sec,
                    easy_text,
                    medium_text,
                    hard_text,
                    total_pct_text,
                    score_text,
                )
        except Exception as e:
            pass
    
    def _format_difficulty_percentage(self, percentage: float) -> Text:
        """Formata porcentagem de dificuldade com cor"""
        if percentage >= 80:
            style = "green"
        elif percentage >= 50:
            style = "yellow"
        elif percentage > 0:
            style = "red"
        else:
            style = "dim"
        
        return Text(f"{percentage:.0f}%", style=style)
    
    def _truncate_model_name(self, name: str, max_length: int = 15) -> str:
        """Truncate model name for display"""
        if len(name) <= max_length:
            return name
        return name[:max_length - 3] + "..."
    
    def update_from_results(self, results: List[CompletedRunSummary]) -> None:
        """Public method to update the widget from results list"""
        self.results = results
    
    def add_result(self, result: CompletedRunSummary) -> None:
        """Add a single result to the table"""
        current = list(self.results)
        
        # Check if this run already exists (update if so)
        for i, existing in enumerate(current):
            if existing.model == result.model and existing.architecture == result.architecture:
                current[i] = result
                self.results = current
                return
        
        # Add new result
        current.append(result)
        self.results = current
