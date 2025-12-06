"""
History Table Widget - Main widget file.
Delegates to submodules for data loading, formatting and table building.
"""
from textual.app import ComposeResult
from textual.widgets import DataTable, Static, Input, Select, SelectionList, Button
from textual.widgets.selection_list import Selection
from textual.containers import Vertical, Horizontal
from typing import List, Dict, Optional, Set
from pathlib import Path

from .data_loader import HistoryDataLoader
from .styles import WIDGET_CSS, AVAILABLE_COLUMNS, SORT_OPTIONS
from .table_builder import filter_data, sort_data, build_table_columns, add_table_row


class HistoryTableWidget(Static):
    """
    Widget de comparação de resultados entre diferentes execuções.
    Mostra questões como linhas e modelos/arquiteturas como colunas.
    """
    
    DEFAULT_CSS = WIDGET_CSS
    _sort_column: Optional[str] = None
    _sort_reverse: bool = False
    _current_sort: Optional[str] = "id_asc"
    
    def __init__(self, results_dir: str = "./results/", dataset_path: str = "./data/dataset.jsonl", **kwargs):
        super().__init__(**kwargs)
        self._data_loader = HistoryDataLoader(Path(results_dir), Path(dataset_path))
        self._selected_configs: Set[str] = set()
        self._selected_columns: Set[str] = {"score"}
        self._table_data: List[Dict] = []
        self._current_search = ""
        self._current_difficulty = "all"
        self._current_sort = "id_asc"
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📊 Histórico de Comparação (H para fechar)", classes="section-header")
            with Horizontal(classes="filters-row"):
                yield Static("🔍", classes="filter-label")
                yield Input(placeholder="Pesquisar questão...", id="search-input")
                yield Static("📊", classes="filter-label")
                yield Select(
                    [("Todas", "all"), ("Fácil", "easy"), ("Médio", "medium"), ("Difícil", "hard")],
                    value="all", id="difficulty-filter", allow_blank=False,
                )
                yield Static("🔃", classes="filter-label")
                yield Select(SORT_OPTIONS, value="id_asc", id="sort-filter", allow_blank=False)
                yield Button("📊 Modelos ▼", id="toggle-models-btn", variant="default")
                yield Button("📋 Colunas ▼", id="toggle-columns-btn", variant="default")
            with Vertical(id="model-selection-container"):
                yield SelectionList[str](id="model-selection-list")
            with Vertical(id="column-selection-container"):
                yield SelectionList[str](id="column-selection-list")
            yield DataTable(id="history-table", zebra_stripes=True, cursor_type="row")
    
    def on_mount(self) -> None:
        """Inicializa e carrega dados"""
        self._data_loader.load_dataset_difficulties()
        self._data_loader.load_all_results()
        self._populate_selections()
        self._build_table()
    
    def _populate_selections(self) -> None:
        """Popula listas de seleção de modelos e colunas"""
        try:
            # Modelos
            model_list = self.query_one("#model-selection-list", SelectionList)
            model_list.clear_options()
            for config in self._data_loader.configs:
                model, arch = config.split("|")
                label = f"{model} ({'Simple' if arch == 'simple' else 'Multi-Agent'})"
                model_list.add_option(Selection(label, config, initial_state=True))
            self._selected_configs = set(self._data_loader.configs)
            
            # Colunas
            col_list = self.query_one("#column-selection-list", SelectionList)
            col_list.clear_options()
            for key, label in AVAILABLE_COLUMNS.items():
                col_list.add_option(Selection(label, key, initial_state=key == "score"))
            self._selected_columns = {"score"}
        except Exception:
            pass
    
    # ==================== Event Handlers ====================
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Toggle containers de seleção"""
        toggles = {
            "toggle-models-btn": ("model-selection-container", "📊 Modelos"),
            "toggle-columns-btn": ("column-selection-container", "📋 Colunas"),
        }
        if event.button.id in toggles:
            container_id, label = toggles[event.button.id]
            self._toggle_container(container_id, event.button.id, label)
    
    def _toggle_container(self, container_id: str, btn_id: str, label: str) -> None:
        try:
            container = self.query_one(f"#{container_id}")
            btn = self.query_one(f"#{btn_id}", Button)
            is_visible = container.has_class("visible")
            container.remove_class("visible") if is_visible else container.add_class("visible")
            btn.label = f"{label} {'▼' if is_visible else '▲'}"
        except Exception:
            pass
    
    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        if event.selection_list.id == "model-selection-list":
            self._selected_configs = set(event.selection_list.selected)
        elif event.selection_list.id == "column-selection-list":
            self._selected_columns = set(event.selection_list.selected)
        self._rebuild_filtered_table()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._current_search = event.value.lower()
            self._rebuild_filtered_table()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "difficulty-filter":
            self._current_difficulty = str(event.value)
            self._rebuild_filtered_table()
        elif event.select.id == "sort-filter":
            self._current_sort = str(event.value)
            self._rebuild_filtered_table()
    
    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key)
        self._sort_reverse = not self._sort_reverse if self._sort_column == col else False
        self._sort_column = col
        # Reseta o sort do Select quando clica no header
        self._current_sort = None
        self._rebuild_filtered_table()
    
    # ==================== Table Building ====================
    
    def _build_table(self) -> None:
        self._table_data = self._data_loader.build_table_data()
        self._rebuild_filtered_table()
    
    def _rebuild_filtered_table(self) -> None:
        try:
            table = self.query_one("#history-table", DataTable)
            display_configs = [c for c in self._data_loader.configs if c in self._selected_configs]
            
            build_table_columns(table, display_configs, self._selected_columns)
            
            filtered = filter_data(self._table_data, self._current_search, self._current_difficulty)
            
            # Usa _current_sort se definido, senão usa o clique no header
            if self._current_sort:
                sorted_data = sort_data(filtered, self._current_sort, False, display_configs, use_select_sort=True)
            else:
                sorted_data = sort_data(filtered, self._sort_column or "", self._sort_reverse, display_configs, use_select_sort=False)
            
            for row_data in sorted_data:
                add_table_row(table, row_data, display_configs, self._selected_columns)
        except Exception:
            pass
    
    def refresh_data(self) -> None:
        """Recarrega todos os dados"""
        self._data_loader.load_dataset_difficulties()
        self._data_loader.load_all_results()
        self._populate_selections()
        self._build_table()
