"""
Current Run Widget - Shows current execution status
Displays the overall configuration and progress of the running benchmark.
This widget is READ-ONLY - it only displays state, doesn't execute anything.
"""
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive
from typing import Optional

from ..state.models import RunState
from ..utils.formatters import format_tokens, format_time_elapsed, format_time
from .current_run_utils import calculate_difficulty_stats, WIDGET_CSS


class CurrentRunWidget(Static):
    """
    Widget displaying current execution information in compact format.
    """
    
    DEFAULT_CSS = WIDGET_CSS
    run_state: reactive[Optional[RunState]] = reactive(None, layout=True)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📊 Execução Atual", classes="section-header", id="config-header")
            yield Static("🤖 Modelo: - 🏗️  Arquitetura: -", classes="info-line", id="info-line-1")
            yield Static("⏱️  Tempo Total: 00:00:00 | 🤖 Tempo Modelo: 00:00:00", classes="info-line", id="time-line")
            yield Static("🟢 Easy: 0 (0.0%) 🟡 Medium: 0 (0.0%) 🔴 Hard: 0 (0.0%)", classes="info-line", id="difficulty-line")
            yield Static("📊 Total: 0/0 (0.0%) Score: 0.0%", classes="info-line", id="total-line")
            yield Static("💾 Tokens: In: 0 | Out: 0", classes="info-line", id="tokens-line")
            yield Static("📋 Questão Atual: - (0/0)", classes="info-line", id="question-line")
    
    def watch_run_state(self, state: Optional[RunState]) -> None:
        if state is None:
            self._reset_display()
        else:
            self._update_display(state)
    
    def _reset_display(self) -> None:
        try:
            self.query_one("#info-line-1", Static).update("🤖 Modelo: - 🏗️  Arquitetura: -")
            self.query_one("#time-line", Static).update("⏱️  Tempo Total: 00:00:00 | 🤖 Tempo Modelo: 00:00:00")
            self.query_one("#difficulty-line", Static).update("🟢 Easy: 0 (0.0%) 🟡 Medium: 0 (0.0%) 🔴 Hard: 0 (0.0%)")
            self.query_one("#total-line", Static).update("📊 Total: 0/0 (0.0%) Score: 0.0%")
            self.query_one("#tokens-line", Static).update("💾 Tokens: In: 0 | Out: 0")
            self.query_one("#question-line", Static).update("📋 Questão Atual: - (0/0)")
        except Exception:
            pass
    
    def _update_display(self, state: RunState) -> None:
        try:
            # Line 1: Model and Architecture
            self.query_one("#info-line-1", Static).update(
                f"🤖 Modelo: {state.model} 🏗️  Arquitetura: {state.architecture}"
            )
            
            # Line 2: Times
            total_time_str = format_time_elapsed(state.started_at)
            model_time_seconds = sum(r.total_time for r in state.results)
            model_time_str = format_time(model_time_seconds)
            self.query_one("#time-line", Static).update(
                f"⏱️  Tempo Total: {total_time_str} | 🤖 Tempo Modelo: {model_time_str}"
            )
            
            # Line 3: Difficulty stats
            diff_stats = calculate_difficulty_stats(state.results)
            easy, medium, hard = diff_stats["easy"], diff_stats["medium"], diff_stats["hard"]
            self.query_one("#difficulty-line", Static).update(
                f"🟢 Easy: {easy['completed']} ({easy['avg_percentage']:.1f}%) "
                f"🟡 Medium: {medium['completed']} ({medium['avg_percentage']:.1f}%) "
                f"🔴 Hard: {hard['completed']} ({hard['avg_percentage']:.1f}%)"
            )
            
            # Line 4: Total stats and score
            total_completed = state.completed_questions
            total_questions = state.total_questions
            total_pct = (total_completed / total_questions * 100) if total_questions > 0 else 0.0
            score = state.calculate_score()
            self.query_one("#total-line", Static).update(
                f"📊 Total: {total_completed}/{total_questions} ({total_pct:.1f}%) Score: {score:.1f}%"
            )
            
            # Line 5: Tokens
            self.query_one("#tokens-line", Static).update(
                f"💾 Tokens: In: {format_tokens(state.total_input_tokens)} | Out: {format_tokens(state.total_output_tokens)}"
            )
            
            # Line 6: Current Question
            if state.current_question:
                q = state.current_question
                self.query_one("#question-line", Static).update(
                    f"📋 Questão Atual: {q.question_id} ({state.completed_questions + 1}/{total_questions})"
                )
            else:
                self.query_one("#question-line", Static).update(
                    f"📋 Questão Atual: - ({state.completed_questions}/{total_questions})"
                )
        except Exception:
            pass
    
    def update_from_state(self, state: Optional[RunState]) -> None:
        self.run_state = state
