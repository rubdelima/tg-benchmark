"""
History Table Widget - Shows comparison of results across different runs
Displays questions as rows and model/architecture combinations as columns
Includes search, filtering by difficulty/model, and sortable columns
"""
from textual.app import ComposeResult
from textual.widgets import DataTable, Static, Input, Select, SelectionList, Collapsible
from textual.widgets.selection_list import Selection
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.events import Key
from textual.message import Message
from rich.text import Text
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import json


# Paletas de cores para alternar entre modelos (mais distintas)
MODEL_COLOR_PALETTES = [
    {"header": "bold white on dark_blue", "score_high": "green on rgb(20,20,50)", "score_mid": "yellow on rgb(20,20,50)", "score_low": "red on rgb(20,20,50)", "dim": "grey50 on rgb(20,20,50)", "bg": "on rgb(20,20,50)"},
    {"header": "bold white on dark_red", "score_high": "bright_green on rgb(50,20,20)", "score_mid": "bright_yellow on rgb(50,20,20)", "score_low": "bright_red on rgb(50,20,20)", "dim": "grey62 on rgb(50,20,20)", "bg": "on rgb(50,20,20)"},
    {"header": "bold white on dark_green", "score_high": "green1 on rgb(20,50,20)", "score_mid": "gold1 on rgb(20,50,20)", "score_low": "red1 on rgb(20,50,20)", "dim": "grey58 on rgb(20,50,20)", "bg": "on rgb(20,50,20)"},
    {"header": "bold white on purple4", "score_high": "spring_green1 on rgb(40,20,50)", "score_mid": "orange1 on rgb(40,20,50)", "score_low": "deep_pink1 on rgb(40,20,50)", "dim": "grey54 on rgb(40,20,50)", "bg": "on rgb(40,20,50)"},
    {"header": "bold white on dark_cyan", "score_high": "cyan on rgb(20,40,50)", "score_mid": "yellow on rgb(20,40,50)", "score_low": "magenta on rgb(20,40,50)", "dim": "grey46 on rgb(20,40,50)", "bg": "on rgb(20,40,50)"},
    {"header": "bold white on grey30", "score_high": "bright_green on rgb(40,40,40)", "score_mid": "bright_yellow on rgb(40,40,40)", "score_low": "bright_red on rgb(40,40,40)", "dim": "grey50 on rgb(40,40,40)", "bg": "on rgb(40,40,40)"},
]


class HistoryTableWidget(Static):
    """
    Widget displaying comparison of results across different runs.
    
    Features:
    - Only shows questions that have been tested
    - Search bar to filter by question ID
    - Filter by difficulty (easy, medium, hard, all)
    - Multi-select models for comparison
    - Sortable columns (click header or press Enter on column)
    - Navigate rows with arrow keys
    - Alternating color palettes per model for visual separation
    - Shows Score, Time, and Tokens for each model
    
    Rows: Questions that have results
    Columns: Question, Difficulty, AVG, then for each config: Score | Time | Tokens
    """
    
    DEFAULT_CSS = """
    HistoryTableWidget {
        width: 100%;
        height: 100%;
        border: solid $primary;
    }
    
    HistoryTableWidget > Vertical {
        height: 100%;
    }
    
    HistoryTableWidget .section-header {
        background: $surface;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }
    
    HistoryTableWidget .filters-row {
        height: 3;
        padding: 0 1;
        background: $surface;
    }
    
    HistoryTableWidget #models-collapsible {
        height: auto;
        max-height: 12;
        background: $surface-darken-1;
    }
    
    HistoryTableWidget #model-selection-list {
        height: auto;
        max-height: 10;
        width: 100%;
        scrollbar-size: 1 1;
    }
    
    HistoryTableWidget #search-input {
        width: 30;
    }
    
    HistoryTableWidget #difficulty-filter {
        width: 15;
    }
    
    HistoryTableWidget #model-filter {
        width: 25;
    }
    
    HistoryTableWidget .filter-label {
        width: auto;
        padding: 0 1;
        content-align: center middle;
    }
    
    HistoryTableWidget DataTable {
        height: 1fr;
    }
    """
    
    # Sorting state
    _sort_column: Optional[str] = None
    _sort_reverse: bool = False
    
    def __init__(self, results_dir: str = "./results/", dataset_path: str = "./data/dataset.jsonl", **kwargs):
        super().__init__(**kwargs)
        self.results_dir = Path(results_dir)
        self.dataset_path = Path(dataset_path)
        self._all_results: Dict[str, Dict] = {}  # {model_arch: {question_id: result}}
        self._questions: Dict[str, Dict] = {}  # {question_id: {difficulty, ...}}
        self._dataset_difficulties: Dict[str, str] = {}  # {question_id: difficulty}
        self._configs: List[str] = []  # List of model|arch configs (sorted alphabetically)
        self._selected_configs: Set[str] = set()  # Configs selected for comparison
        self._config_palette: Dict[str, Dict] = {}  # {config: palette}
        self._table_data: List[Dict] = []  # Raw table data for sorting/filtering
        self._current_search = ""
        self._current_difficulty = "all"
        self._current_model = "all"  # For question filter (show questions tested with this model)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📊 Histórico de Comparação (H para fechar) - Clique no cabeçalho para ordenar | ↑↓ navegar", classes="section-header")
            with Horizontal(classes="filters-row"):
                yield Static("🔍", classes="filter-label")
                yield Input(placeholder="Pesquisar questão...", id="search-input")
                yield Static("📊", classes="filter-label")
                yield Select(
                    [("Todas", "all"), ("Fácil", "easy"), ("Médio", "medium"), ("Difícil", "hard")],
                    value="all",
                    id="difficulty-filter",
                    allow_blank=False,
                )
                yield Static("🎯", classes="filter-label")
                yield Select(
                    [("Todas Questões", "all")],
                    value="all",
                    id="model-filter",
                    allow_blank=False,
                )
            with Collapsible(title="📊 Modelos para comparar (clique para expandir)", collapsed=True, id="models-collapsible"):
                yield SelectionList[str](id="model-selection-list")
            yield DataTable(id="history-table", zebra_stripes=False, cursor_type="row")
    
    def on_mount(self) -> None:
        """Initialize and load data"""
        self._load_dataset_difficulties()
        self._load_all_results()
        self._assign_color_palettes()
        self._update_model_filter_options()
        self._populate_selection_list()
        self._build_table()
        
        # Setup table for row navigation
        table = self.query_one("#history-table", DataTable)
        table.cursor_type = "row"
    
    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """Handle selection changes in the model SelectionList"""
        if event.selection_list.id == "model-selection-list":
            # Update selected configs from the SelectionList
            self._selected_configs = set(event.selection_list.selected)
            self._rebuild_filtered_table()
    
    def _populate_selection_list(self) -> None:
        """Populate the SelectionList with all model/arch configs"""
        try:
            selection_list = self.query_one("#model-selection-list", SelectionList)
            selection_list.clear_options()
            
            # Build selections for each config
            selections = []
            for config in self._configs:
                model, arch = config.split("|")
                short_name = self._short_name(model, arch)
                palette = self._config_palette.get(config, MODEL_COLOR_PALETTES[0])
                
                # Create styled label
                arch_label = "Simple" if arch == "simple" else "Multi-Agent"
                display_label = f"{model} ({arch_label})"
                
                # By default all are selected
                selections.append(Selection(display_label, config, initial_state=True))
            
            # Add all selections
            selection_list.add_options(selections)
            
            # Update selected configs set
            self._selected_configs = set(self._configs)
        except Exception:
            pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        if event.input.id == "search-input":
            self._current_search = event.value.lower()
            self._rebuild_filtered_table()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter selection changes"""
        if event.select.id == "difficulty-filter":
            self._current_difficulty = str(event.value)
            self._rebuild_filtered_table()
        elif event.select.id == "model-filter":
            self._current_model = str(event.value)
            self._rebuild_filtered_table()
    
    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click for sorting"""
        column_key = str(event.column_key)
        
        # Toggle sort direction if same column, else sort ascending
        if self._sort_column == column_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column_key
            self._sort_reverse = False
        
        self._rebuild_filtered_table()
    
    def _load_dataset_difficulties(self) -> None:
        """Load difficulties from the dataset.jsonl file"""
        self._dataset_difficulties = {}
        
        if not self.dataset_path.exists():
            return
        
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        q_id = data.get("question_id")
                        difficulty = data.get("difficulty", "unknown")
                        if q_id:
                            self._dataset_difficulties[q_id] = difficulty
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    
    def _load_all_results(self) -> None:
        """Load all results from results directory - only questions that have been tested"""
        self._all_results = {}
        self._questions = {}
        self._configs = []
        
        if not self.results_dir.exists():
            return
        
        for result_file in self.results_dir.glob("*.json"):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                model = data.get("model", "unknown")
                arch = data.get("architecture", "unknown")
                key = f"{model}|{arch}"
                
                if key not in self._configs:
                    self._configs.append(key)
                
                self._all_results[key] = {}
                
                for result in data.get("results", []):
                    q_id = result.get("question_id")
                    if q_id:
                        self._all_results[key][q_id] = result
                        
                        # Store question metadata - only for tested questions
                        if q_id not in self._questions:
                            difficulty = self._dataset_difficulties.get(
                                q_id, 
                                result.get("difficulty", "unknown")
                            )
                            self._questions[q_id] = {
                                "difficulty": difficulty,
                            }
            except Exception:
                pass
        
        # Sort configs alphabetically
        self._configs.sort()
        
        # By default, select all configs
        self._selected_configs = set(self._configs)
    
    def _assign_color_palettes(self) -> None:
        """Assign alternating color palettes to each config"""
        self._config_palette = {}
        for i, config in enumerate(self._configs):
            palette_idx = i % len(MODEL_COLOR_PALETTES)
            self._config_palette[config] = MODEL_COLOR_PALETTES[palette_idx]
    
    def _update_model_filter_options(self) -> None:
        """Update model filter dropdown with available models"""
        try:
            model_select = self.query_one("#model-filter", Select)
            options = [("Todos Modelos", "all")]
            
            for config in self._configs:
                model, arch = config.split("|")
                short_name = self._short_name(model, arch)
                options.append((short_name, config))
            
            model_select.set_options(options)
        except Exception:
            pass
    
    def _build_table_data(self) -> None:
        """Build raw table data for sorting/filtering"""
        self._table_data = []
        
        for q_id, q_info in self._questions.items():
            # Calculate AVG across all configs
            scores = []
            config_data = {}
            
            for config in self._configs:
                result = self._all_results.get(config, {}).get(q_id)
                if result:
                    score = result.get("success_rate", 0) * 100
                    time_taken = result.get("total_time", 0)
                    tokens_in = result.get("total_input_tokens", 0) or 0
                    tokens_out = result.get("total_output_tokens", 0) or 0
                    total_tokens = tokens_in + tokens_out
                    
                    scores.append(score)
                    config_data[config] = {
                        "score": score,
                        "time": time_taken,
                        "tokens": total_tokens,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                    }
                else:
                    config_data[config] = None
            
            avg_score = sum(scores) / len(scores) if scores else 0
            
            self._table_data.append({
                "question_id": q_id,
                "difficulty": q_info["difficulty"],
                "avg": avg_score,
                "config_data": config_data,
            })
    
    def _filter_and_sort_data(self) -> List[Dict]:
        """Apply filters and sorting to table data"""
        filtered = self._table_data.copy()
        
        # Apply search filter
        if self._current_search:
            filtered = [
                row for row in filtered 
                if self._current_search in row["question_id"].lower()
            ]
        
        # Apply difficulty filter
        if self._current_difficulty != "all":
            filtered = [
                row for row in filtered 
                if row["difficulty"] == self._current_difficulty
            ]
        
        # Apply model filter (show only questions tested with this model)
        if self._current_model != "all":
            filtered = [
                row for row in filtered 
                if row["config_data"].get(self._current_model) is not None
            ]
        
        # Apply sorting
        if self._sort_column:
            difficulty_order = {"easy": 0, "medium": 1, "hard": 2, "unknown": 3}
            
            if self._sort_column == "Question":
                filtered.sort(key=lambda x: x["question_id"], reverse=self._sort_reverse)
            elif self._sort_column == "Diff":
                filtered.sort(
                    key=lambda x: difficulty_order.get(x["difficulty"], 3), 
                    reverse=self._sort_reverse
                )
            elif self._sort_column == "AVG":
                filtered.sort(key=lambda x: x["avg"], reverse=self._sort_reverse)
            else:
                # Sort by specific config column (Score, Time, or Tokens)
                for config in self._configs:
                    short_name = self._short_name(*config.split("|"))
                    
                    # Check for Score column
                    if self._sort_column == f"{short_name}|%":
                        filtered.sort(
                            key=lambda x, c=config: (x["config_data"].get(c) or {}).get("score", -1),
                            reverse=self._sort_reverse
                        )
                        break
                    # Check for Time column
                    elif self._sort_column == f"{short_name}|⏱":
                        filtered.sort(
                            key=lambda x, c=config: (x["config_data"].get(c) or {}).get("time", -1),
                            reverse=self._sort_reverse
                        )
                        break
                    # Check for Tokens column
                    elif self._sort_column == f"{short_name}|T":
                        filtered.sort(
                            key=lambda x, c=config: (x["config_data"].get(c) or {}).get("tokens", -1),
                            reverse=self._sort_reverse
                        )
                        break
        else:
            # Default sort: by difficulty then by name
            difficulty_order = {"easy": 0, "medium": 1, "hard": 2, "unknown": 3}
            filtered.sort(key=lambda x: (difficulty_order.get(x["difficulty"], 3), x["question_id"]))
        
        return filtered
    
    def _build_table(self) -> None:
        """Build the comparison table"""
        self._build_table_data()
        self._rebuild_filtered_table()
    
    def _rebuild_filtered_table(self) -> None:
        """Rebuild table with current filters and sorting"""
        try:
            table = self.query_one("#history-table", DataTable)
            table.clear(columns=True)
            
            # Get selected configs for display
            display_configs = [c for c in self._configs if c in self._selected_configs]
            
            if not display_configs or not self._questions:
                table.add_column("Info")
                table.add_row("Nenhum resultado encontrado" if not self._questions else "Selecione ao menos um modelo")
                return
            
            # Build columns: Question, Difficulty, AVG, then for each selected config: Score | Time | Tokens
            columns = [
                ("Question", "Question"),
                ("Diff", "Diff"),
                ("AVG", "AVG"),
            ]
            
            for config in display_configs:
                model, arch = config.split("|")
                short_name = self._short_name(model, arch)
                palette = self._config_palette.get(config, MODEL_COLOR_PALETTES[0])
                # Add 3 columns per config: Score, Time, Tokens
                columns.append((f"{short_name}|%", f"{short_name}|%"))    # Score
                columns.append((f"{short_name}|⏱", f"{short_name}|⏱"))   # Time
                columns.append((f"{short_name}|T", f"{short_name}|T"))    # Tokens
            
            # Add columns with keys
            for label, key in columns:
                table.add_column(label, key=key)
            
            # Get filtered and sorted data
            filtered_data = self._filter_and_sort_data()
            
            if not filtered_data:
                empty_cells = [""] * (len(columns) - 1)
                table.add_row("Nenhuma questão corresponde aos filtros", *empty_cells)
                return
            
            # Build rows
            for row_data in filtered_data:
                row = [
                    row_data["question_id"][:20],  # Truncate long question IDs
                    self._format_difficulty(row_data["difficulty"]),
                    self._format_avg(row_data["avg"], display_configs, row_data["config_data"]),
                ]
                
                for config in display_configs:
                    data = row_data["config_data"].get(config)
                    palette = self._config_palette.get(config, MODEL_COLOR_PALETTES[0])
                    
                    if data is not None:
                        row.append(self._format_score(data["score"], palette))
                        row.append(self._format_time_cell(data["time"], palette))
                        row.append(self._format_tokens(data["tokens"], palette))
                    else:
                        row.append(Text("-", style=palette["dim"]))
                        row.append(Text("-", style=palette["dim"]))
                        row.append(Text("-", style=palette["dim"]))
                
                table.add_row(*row)
            
        except Exception:
            pass
    
    def _short_name(self, model: str, arch: str) -> str:
        """Create short name for column header"""
        if ":" in model:
            parts = model.split(":")
            model_short = parts[0][:5] + ":" + parts[-1][:3]
        else:
            model_short = model[:8]
        arch_short = "S" if arch == "simple" else "M"
        return f"{model_short}|{arch_short}"
    
    def _format_difficulty(self, difficulty: str) -> Text:
        """Format difficulty with color"""
        colors = {"easy": "green", "medium": "yellow", "hard": "red"}
        abbrev = {"easy": "easy", "medium": "med", "hard": "hard", "unknown": "?"}
        return Text(abbrev.get(difficulty, "?"), style=colors.get(difficulty, "white"))
    
    def _format_avg(self, avg: float, display_configs: Optional[List[str]] = None, config_data: Optional[Dict] = None) -> Text:
        """Format AVG score with color - recalculates based on displayed configs"""
        # Recalculate avg if we have specific configs to consider
        if display_configs and config_data:
            scores = []
            for config in display_configs:
                data = config_data.get(config)
                if data and data.get("score") is not None:
                    scores.append(data["score"])
            avg = sum(scores) / len(scores) if scores else 0
        
        if avg >= 80:
            style = "green bold"
        elif avg >= 50:
            style = "yellow"
        elif avg > 0:
            style = "red"
        else:
            style = "dim"
        
        return Text(f"{avg:.0f}%", style=style)
    
    def _format_score(self, score: float, palette: Dict) -> Text:
        """Format score with color from palette"""
        if score >= 80:
            style = palette["score_high"] + " bold"
        elif score >= 50:
            style = palette["score_mid"]
        elif score > 0:
            style = palette["score_low"]
        else:
            style = palette["dim"]
        
        return Text(f"{score:.0f}%", style=style)
    
    def _format_time_cell(self, seconds: float, palette: Dict) -> Text:
        """Format time in readable format with palette color"""
        time_str = self._format_time(seconds)
        
        # Color based on time (shorter is better)
        if seconds < 10:
            style = palette["score_high"]
        elif seconds < 60:
            style = palette["score_mid"]
        else:
            style = palette["score_low"]
        
        return Text(time_str, style=style)
    
    def _format_tokens(self, tokens: int, palette: Dict) -> Text:
        """Format tokens with K/M suffix"""
        if tokens >= 1_000_000:
            token_str = f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            token_str = f"{tokens / 1_000:.1f}K"
        else:
            token_str = str(tokens)
        
        # Color based on token count (fewer is generally better)
        if tokens < 1_000:
            style = palette["score_high"]
        elif tokens < 10_000:
            style = palette["score_mid"]
        else:
            style = palette["score_low"]
        
        return Text(token_str, style=style)
    
    def _format_time(self, seconds: float) -> str:
        """Format time in readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m{secs:02d}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}m"
    
    def refresh_data(self) -> None:
        """Reload all data and rebuild table"""
        self._load_dataset_difficulties()
        self._load_all_results()
        self._assign_color_palettes()
        self._update_model_filter_options()
        self._populate_selection_list()
        self._build_table()
