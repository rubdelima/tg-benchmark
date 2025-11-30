"""
Current Run Widget - Shows current execution status
Displays the overall configuration and progress of the running benchmark.
This widget is READ-ONLY - it only displays state, doesn't execute anything.
"""
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive
from typing import Optional, Dict

from ..state.models import RunState, RunStatus
from ..utils.formatters import format_tokens, format_time_elapsed, format_time


class CurrentRunWidget(Static):
    """
    Widget displaying current execution information in compact format.
    
    Structure:
    ┌─ 📊 Execução Atual ─────────────────────────────────────────────────┐
    │ 🤖 Modelo: qwen3:8b 🏗️  Arquitetura: multi-agent ⏱️  Tempo: 02:25:37 │
    │ 🟢 Easy: 10/30 (33.3%) 🟡 Medium: 5/30 (16.7%) 🔴 Hard: 2/30 (6.7%) │
    │ 📊 Total: 17/90 (18.9%) Score: 15.2% % Total: 0.0%                  │
    │ 💾 Tokens: In: 4.2M | Out: 3.4M                                     │
    │ 📋 Questão Atual: abc301_a (15/90)                                  │
    └─────────────────────────────────────────────────────────────────────┘
    """
    
    DEFAULT_CSS = """
    CurrentRunWidget {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 0;
    }
    
    CurrentRunWidget > Vertical {
        height: auto;
    }
    
    CurrentRunWidget .info-line {
        height: 1;
        padding: 0 1;
    }
    
    CurrentRunWidget .section-header {
        background: $surface;
        text-style: bold;
        padding: 0 1;
    }
    """
    
    # Reactive property for automatic updates
    run_state: reactive[Optional[RunState]] = reactive(None, layout=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        with Vertical():
            # Configuration section header
            yield Static("📊 Execução Atual", classes="section-header", id="config-header")
            
            # Line 1: Model and Architecture
            yield Static("🤖 Modelo: - 🏗️  Arquitetura: -", classes="info-line", id="info-line-1")
            
            # Line 2: Times - Total elapsed and Model execution time
            yield Static("⏱️  Tempo Total: 00:00:00 | 🤖 Tempo Modelo: 00:00:00", classes="info-line", id="time-line")
            
            # Line 3: Difficulty stats - X completed (Y% avg success rate)
            yield Static("🟢 Easy: 0 (0.0%) 🟡 Medium: 0 (0.0%) 🔴 Hard: 0 (0.0%)", classes="info-line", id="difficulty-line")
            
            # Line 4: Total stats and score
            yield Static("📊 Total: 0/0 (0.0%) Score: 0.0%", classes="info-line", id="total-line")
            
            # Line 5: Tokens
            yield Static("💾 Tokens: In: 0 | Out: 0", classes="info-line", id="tokens-line")
            
            # Line 6: Current Question (simplified)
            yield Static("📋 Questão Atual: - (0/0)", classes="info-line", id="question-line")
    
    def watch_run_state(self, state: Optional[RunState]) -> None:
        """React to run_state changes"""
        if state is None:
            self._reset_display()
            return
        
        self._update_display(state)
    
    def _reset_display(self) -> None:
        """Reset all display elements to default values"""
        try:
            self.query_one("#info-line-1", Static).update(
                "🤖 Modelo: - 🏗️  Arquitetura: -"
            )
            self.query_one("#time-line", Static).update(
                "⏱️  Tempo Total: 00:00:00 | 🤖 Tempo Modelo: 00:00:00"
            )
            self.query_one("#difficulty-line", Static).update(
                "🟢 Easy: 0 (0.0%) 🟡 Medium: 0 (0.0%) 🔴 Hard: 0 (0.0%)"
            )
            self.query_one("#total-line", Static).update(
                "📊 Total: 0/0 (0.0%) Score: 0.0%"
            )
            self.query_one("#tokens-line", Static).update("💾 Tokens: In: 0 | Out: 0")
            self.query_one("#question-line", Static).update("📋 Questão Atual: - (0/0)")
        except Exception:
            pass
    
    def _update_display(self, state: RunState) -> None:
        """Update all display elements from state"""
        try:
            # Line 1: Model and Architecture
            self.query_one("#info-line-1", Static).update(
                f"🤖 Modelo: {state.model} 🏗️  Arquitetura: {state.architecture}"
            )
            
            # Line 2: Times
            # Total elapsed time (from started_at to now)
            total_time_str = format_time_elapsed(state.started_at)
            # Model execution time (sum of all question times - more reliable)
            model_time_seconds = sum(
                r.total_time for r in state.results
            )
            model_time_str = format_time(model_time_seconds)
            self.query_one("#time-line", Static).update(
                f"⏱️  Tempo Total: {total_time_str} | 🤖 Tempo Modelo: {model_time_str}"
            )
            
            # Calculate difficulty stats from results
            diff_stats = self._calculate_difficulty_stats(state.results)
            
            # Line 3: Difficulty stats - X executed, Y% average success rate
            easy = diff_stats["easy"]
            medium = diff_stats["medium"]
            hard = diff_stats["hard"]
            self.query_one("#difficulty-line", Static).update(
                f"🟢 Easy: {easy['completed']} ({easy['avg_percentage']:.1f}%) "
                f"🟡 Medium: {medium['completed']} ({medium['avg_percentage']:.1f}%) "
                f"🔴 Hard: {hard['completed']} ({hard['avg_percentage']:.1f}%)"
            )
            
            # Line 4: Total stats and score
            total_completed = state.completed_questions
            total_questions = state.total_questions
            total_percentage = (total_completed / total_questions * 100) if total_questions > 0 else 0.0
            score = state.calculate_score()
            
            self.query_one("#total-line", Static).update(
                f"📊 Total: {total_completed}/{total_questions} ({total_percentage:.1f}%) Score: {score:.1f}%"
            )
            
            # Line 5: Tokens
            in_tokens = format_tokens(state.total_input_tokens)
            out_tokens = format_tokens(state.total_output_tokens)
            self.query_one("#tokens-line", Static).update(
                f"💾 Tokens: In: {in_tokens} | Out: {out_tokens}"
            )
            
            # Line 6: Current Question (simplified - only name and progress)
            if state.current_question:
                q = state.current_question
                q_idx = state.completed_questions + 1
                q_total = state.total_questions
                self.query_one("#question-line", Static).update(
                    f"📋 Questão Atual: {q.question_id} ({q_idx}/{q_total})"
                )
            else:
                self.query_one("#question-line", Static).update(
                    f"📋 Questão Atual: - ({state.completed_questions}/{state.total_questions})"
                )
        except Exception:
            pass
    
    def _calculate_difficulty_stats(self, results) -> Dict[str, Dict]:
        """
        Calculate difficulty statistics from results.
        
        Returns for each difficulty:
        - completed: number of questions executed
        - total_success_rate: sum of success_rates
        - avg_percentage: average success_rate as percentage (0-100)
        """
        stats = {
            "easy": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
            "medium": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
            "hard": {"completed": 0, "total_success_rate": 0.0, "avg_percentage": 0.0},
        }
        
        for result in results:
            diff = result.difficulty if hasattr(result, 'difficulty') else result.get("difficulty", "medium")
            if diff in stats:
                stats[diff]["completed"] += 1
                success_rate = result.success_rate if hasattr(result, 'success_rate') else result.get("success_rate", 0)
                stats[diff]["total_success_rate"] += success_rate
        
        # Calculate average percentage for each difficulty
        for diff in stats:
            if stats[diff]["completed"] > 0:
                stats[diff]["avg_percentage"] = (stats[diff]["total_success_rate"] / stats[diff]["completed"]) * 100
        
        return stats
    
    def _get_status_text(self, status: RunStatus) -> str:
        """Get human-readable status text"""
        status_texts = {
            RunStatus.IDLE: "Aguardando",
            RunStatus.LOADING_MODEL: "Carregando modelo",
            RunStatus.GENERATING_CODE: "Gerando código",
            RunStatus.RUNNING_TESTS: "Executando testes",
            RunStatus.SAVING_RESULTS: "Salvando resultados",
            RunStatus.COMPLETED: "Concluído",
            RunStatus.ERROR: "Erro",
        }
        return status_texts.get(status, "Desconhecido")
    
    def _get_status_icon(self, status: RunStatus) -> str:
        """Get status icon"""
        status_icons = {
            RunStatus.IDLE: "⏸️",
            RunStatus.LOADING_MODEL: "⏳",
            RunStatus.GENERATING_CODE: "💻",
            RunStatus.RUNNING_TESTS: "🧪",
            RunStatus.SAVING_RESULTS: "💾",
            RunStatus.COMPLETED: "✅",
            RunStatus.ERROR: "❌",
        }
        return status_icons.get(status, "❓")
    
    def update_from_state(self, state: Optional[RunState]) -> None:
        """Public method to update the widget from a state object"""
        self.run_state = state
