"""
Results Table Widget - Main widget file.
"""
from textual.app import ComposeResult
from textual.widgets import DataTable, Static, Select, SelectionList, Button
from textual.widgets.selection_list import Selection
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from rich.text import Text
from typing import List, Optional, Any, Set

from ...state.models import CompletedRunSummary
from ...utils.formatters import format_tokens
from .styles import WIDGET_CSS, COLUMNS, SORT_OPTIONS
from .formatters import (
    format_time, format_difficulty_stats, format_score, truncate_model_name
)


class ResultsTableWidget(Static):
    """
    Widget exibindo resultados de execuções concluídas.
    Suporta ordenação por clique no cabeçalho das colunas.
    """
    
    DEFAULT_CSS = WIDGET_CSS
    results: reactive[List[CompletedRunSummary]] = reactive(list, layout=True)
    
    _sort_column: Optional[str] = None
    _sort_reverse: bool = False
    _selected_models: Set[str] = set()
    _current_arch: str = "all"
    _current_sort: str = "score_desc"
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📈 Resultados Concluídos", classes="section-header")
            with Horizontal(classes="filters-row"):
                yield Static("🏗️", classes="filter-label")
                yield Select(
                    [("Todas Arq.", "all"), ("Simple", "simple"), ("Multi", "multi-agent")],
                    value="all", id="arch-filter", allow_blank=False,
                )
                yield Static("📊", classes="filter-label")
                yield Select(SORT_OPTIONS, value="score_desc", id="sort-filter", allow_blank=False)
                yield Button("🔍 Modelos ▼", id="toggle-models-btn", variant="default")
            with Vertical(id="model-selection-container"):
                yield SelectionList[str](id="model-selection-list")
            yield DataTable(id="results-table", zebra_stripes=True)
    
    def on_mount(self) -> None:
        """Inicializa colunas da tabela"""
        table = self.query_one("#results-table", DataTable)
        for label, key in COLUMNS:
            table.add_column(label, key=key)
        table.cursor_type = "row"
    
    # ==================== Event Handlers ====================
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-models-btn":
            self._toggle_model_container()
    
    def _toggle_model_container(self) -> None:
        try:
            container = self.query_one("#model-selection-container")
            btn = self.query_one("#toggle-models-btn", Button)
            is_visible = container.has_class("visible")
            container.remove_class("visible") if is_visible else container.add_class("visible")
            btn.label = f"🔍 Modelos {'▼' if is_visible else '▲'}"
        except Exception:
            pass
    
    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        if event.selection_list.id == "model-selection-list":
            self._selected_models = set(event.selection_list.selected)
            self._rebuild_table()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "arch-filter":
            self._current_arch = str(event.value)
        elif event.select.id == "sort-filter":
            self._current_sort = str(event.value)
        self._rebuild_table()
    
    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key)
        self._sort_reverse = not self._sort_reverse if self._sort_column == col else False
        self._sort_column = col
        self._rebuild_table()
    
    def watch_results(self, results: List[CompletedRunSummary]) -> None:
        self._update_model_selection(results)
        self._rebuild_table()
    
    # ==================== Selection & Filtering ====================
    
    def _update_model_selection(self, results: List[CompletedRunSummary]) -> None:
        try:
            selection_list = self.query_one("#model-selection-list", SelectionList)
            selection_list.clear_options()
            unique_models = set(r.model for r in results)
            for model in sorted(unique_models):
                selection_list.add_option(Selection(model, model, initial_state=True))
            self._selected_models = unique_models
        except Exception:
            pass
    
    def _filter_results(self) -> List[CompletedRunSummary]:
        filtered = []
        for result in self.results:
            if self._selected_models and result.model not in self._selected_models:
                continue
            if self._current_arch != "all":
                if self._current_arch == "simple" and result.architecture != "simple":
                    continue
                if self._current_arch == "multi-agent" and result.architecture == "simple":
                    continue
            filtered.append(result)
        return filtered
    
    def _get_sort_value(self, result: CompletedRunSummary) -> Any:
        sort_key = self._current_sort.replace("_asc", "").replace("_desc", "")
        values = {
            "model": result.model.lower(),
            "score": result.score,
            "time": result.total_time,
            "tks": result.tokens_per_second,
        }
        return values.get(sort_key, 0)
    
    # ==================== Table Building ====================
    
    def _rebuild_table(self) -> None:
        try:
            table = self.query_one("#results-table", DataTable)
            table.clear()
            
            filtered = self._filter_results()
            reverse = self._current_sort.endswith("_desc")
            sorted_results = sorted(filtered, key=self._get_sort_value, reverse=reverse)
            
            for result in sorted_results:
                self._add_result_row(table, result)
        except Exception:
            pass
    
    def _add_result_row(self, table: DataTable, result: CompletedRunSummary) -> None:
        model_text = truncate_model_name(result.model)
        arch_text = "simple" if result.architecture == "simple" else "multi"
        tokens_out = format_tokens(result.total_output_tokens)
        total_time = Text(format_time(result.total_time).rjust(8))
        
        avg_time_val = result.total_time / result.total_questions if result.total_questions > 0 else 0
        avg_time = Text(format_time(avg_time_val).rjust(8))
        tks_per_sec = Text(f"{result.tokens_per_second:.1f}".rjust(6))
        
        easy = format_difficulty_stats(result.easy_passed, result.easy_total, result.easy_percentage)
        medium = format_difficulty_stats(result.medium_passed, result.medium_total, result.medium_percentage)
        hard = format_difficulty_stats(result.hard_passed, result.hard_total, result.hard_percentage)
        
        total_passed = result.easy_passed + result.medium_passed + result.hard_passed
        total_questions = result.easy_total + result.medium_total + result.hard_total
        total_pct = (total_passed / total_questions * 100) if total_questions > 0 else 0
        total = format_difficulty_stats(total_passed, total_questions, total_pct)
        
        score = format_score(result.score)
        
        table.add_row(model_text, arch_text, tokens_out, total_time, avg_time, 
                      tks_per_sec, easy, medium, hard, total, score)
    
    # ==================== Public Methods ====================
    
    def update_from_results(self, results: List[CompletedRunSummary]) -> None:
        self.results = results
    
    def add_result(self, result: CompletedRunSummary) -> None:
        current = list(self.results)
        for i, existing in enumerate(current):
            if existing.model == result.model and existing.architecture == result.architecture:
                current[i] = result
                self.results = current
                return
        current.append(result)
        self.results = current
