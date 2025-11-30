"""
Progress Bars Widget - Shows overall and current progress
Two progress bars: launcher progress and current run progress
Uses custom Rich-based progress bar for full width control
"""
from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical
from textual.reactive import reactive
from rich.text import Text
from rich.console import RenderableType
from typing import Optional

from ..state.models import LauncherState, RunState


class CustomProgressBar(Static):
    """A custom progress bar widget using Rich Text for full control."""
    
    DEFAULT_CSS = """
    CustomProgressBar {
        width: 100%;
        height: 1;
    }
    """
    
    progress: reactive[float] = reactive(0.0)
    label: reactive[str] = reactive("")
    info: reactive[str] = reactive("")
    
    def __init__(
        self,
        label: str = "",
        bar_color: str = "green",
        bg_color: str = "grey23",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.label = label
        self.bar_color = bar_color
        self.bg_color = bg_color
        self._current = 0
        self._total = 0
    
    def render(self) -> RenderableType:
        """Render the progress bar."""
        # Get available width
        width = self.size.width
        if width <= 0:
            width = 80
        
        # Calculate component widths
        label_text = f"{self.label} "
        label_len = len(label_text)
        
        # Info text (e.g., "5/18 (27.8%)")
        info_text = f" {self.info}"
        info_len = len(info_text)
        
        # Bar width = total width - label - info - brackets
        bar_width = width - label_len - info_len - 2  # -2 for [ ]
        if bar_width < 10:
            bar_width = 10
        
        # Calculate filled portion
        if self._total > 0:
            filled = int((self._current / self._total) * bar_width)
        else:
            filled = 0
        
        filled = min(filled, bar_width)
        empty = bar_width - filled
        
        # Build the text
        result = Text()
        result.append(label_text, style="bold")
        result.append("[", style="dim")
        result.append("█" * filled, style=self.bar_color)
        result.append("░" * empty, style=self.bg_color)
        result.append("]", style="dim")
        result.append(info_text, style="cyan")
        
        return result
    
    def update_progress(self, current: int, total: int) -> None:
        """Update the progress bar."""
        self._current = current
        self._total = total
        
        if total > 0:
            self.progress = current / total
            percentage = (current / total) * 100
            self.info = f"{current}/{total} ({percentage:.1f}%)"
        else:
            self.progress = 0.0
            self.info = "0/0 (0.0%)"
        
        self.refresh()
    
    def watch_progress(self, progress: float) -> None:
        """React to progress changes."""
        self.refresh()


class ProgressBarsWidget(Static):
    """
    Widget displaying two progress bars at the bottom of the screen.
    
    Structure:
    ┌─────────────────────────────────────────────────────────────────┐
    │ 📦 Progresso Total (Modelos): [████████░░░░░░░░░░] 5/18 (27.8%)│
    │ 📝 Progresso Atual (Questões): [██████████░░░░░░░] 15/100 (15%)│
    └─────────────────────────────────────────────────────────────────┘
    """
    
    DEFAULT_CSS = """
    ProgressBarsWidget {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 0 1;
    }
    
    ProgressBarsWidget > Vertical {
        width: 100%;
        height: auto;
    }
    
    ProgressBarsWidget CustomProgressBar {
        width: 100%;
        height: 1;
    }
    """
    
    # Reactive properties
    launcher_progress: reactive[tuple] = reactive((0, 0), layout=True)
    run_progress: reactive[tuple] = reactive((0, 0), layout=True)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield CustomProgressBar(
                label="📦 Progresso Total (Modelos):",
                bar_color="bright_blue",
                id="launcher-progress"
            )
            yield CustomProgressBar(
                label="📝 Progresso Atual (Questões):",
                bar_color="bright_green",
                id="run-progress"
            )
    
    def watch_launcher_progress(self, progress: tuple) -> None:
        """React to launcher progress changes"""
        current, total = progress
        try:
            bar = self.query_one("#launcher-progress", CustomProgressBar)
            bar.update_progress(current, total)
        except Exception:
            pass
    
    def watch_run_progress(self, progress: tuple) -> None:
        """React to run progress changes"""
        current, total = progress
        try:
            bar = self.query_one("#run-progress", CustomProgressBar)
            bar.update_progress(current, total)
        except Exception:
            pass
    
    def update_launcher_progress(self, current: int, total: int) -> None:
        """Public method to update launcher progress"""
        self.launcher_progress = (current, total)
    
    def update_run_progress(self, current: int, total: int) -> None:
        """Public method to update run progress"""
        self.run_progress = (current, total)
    
    def update_from_states(
        self,
        launcher_state: Optional[LauncherState],
        run_state: Optional[RunState]
    ) -> None:
        """Update both progress bars from state objects"""
        if launcher_state:
            self.launcher_progress = (
                launcher_state.completed_runs,
                launcher_state.total_runs
            )
        else:
            self.launcher_progress = (0, 0)
        
        if run_state:
            self.run_progress = (
                run_state.completed_questions,
                run_state.total_questions
            )
        else:
            self.run_progress = (0, 0)
    
    def reset(self) -> None:
        """Reset both progress bars"""
        self.launcher_progress = (0, 0)
        self.run_progress = (0, 0)
