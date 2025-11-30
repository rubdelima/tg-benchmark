"""
State Models for TUI
Pydantic models for state management between processes
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    """Status of the current run"""
    IDLE = "idle"
    LOADING_MODEL = "loading_model"
    GENERATING_CODE = "generating_code"
    RUNNING_TESTS = "running_tests"
    SAVING_RESULTS = "saving_results"
    COMPLETED = "completed"
    ERROR = "error"


class DifficultyStats(BaseModel):
    """Estatísticas por dificuldade"""
    total: int = 0
    passed: int = 0
    percentage: float = 0.0


class QuestionResult(BaseModel):
    """Result of a single question execution"""
    question_id: str
    difficulty: str = "unknown"
    total_time: float = 0.0
    passed_tests: int = 0
    total_tests: int = 0
    success_rate: float = 0.0
    code_generation_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    traceback: Optional[str] = None


class QuestionState(BaseModel):
    """State of the current question being processed"""
    question_id: str
    difficulty: str = "unknown"
    title: str = ""
    index: int = 0  # Current question index (1-based)
    total: int = 0  # Total questions
    status: RunStatus = RunStatus.IDLE
    started_at: Optional[datetime] = None
    input_tokens: int = 0
    output_tokens: int = 0
    # Test case progress
    current_test: int = 0
    total_tests: int = 0
    passed_tests: int = 0


class RunState(BaseModel):
    """State of a single main.py execution"""
    model: str
    architecture: str
    status: RunStatus = RunStatus.IDLE
    started_at: Optional[datetime] = None
    
    # Overall progress
    total_questions: int = 0
    completed_questions: int = 0
    
    # Current question
    current_question: Optional[QuestionState] = None
    
    # Accumulated metrics
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    current_score: float = 0.0
    
    # Partial results for recovery
    results: List[QuestionResult] = Field(default_factory=list)
    
    def calculate_score(self) -> float:
        """
        Calculate weighted score based on success_rate of each result.
        Weights: easy=1, medium=3, hard=5
        Score = sum(success_rate * weight) / sum(weights) * 100
        """
        if not self.results:
            return 0.0
        
        weights = {"easy": 1, "medium": 3, "hard": 5}
        total_weighted = 0.0
        total_weight = 0.0
        
        for result in self.results:
            weight = weights.get(result.difficulty, 1)
            total_weighted += result.success_rate * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return (total_weighted / total_weight) * 100


class GridItem(BaseModel):
    """A single item in the execution grid"""
    model: str
    architecture: str
    completed: bool = False
    result_file: Optional[str] = None


class LauncherState(BaseModel):
    """State of the tests_launcher.py execution"""
    grid: List[GridItem] = Field(default_factory=list)
    total_runs: int = 0
    completed_runs: int = 0
    current_index: int = 0
    started_at: Optional[datetime] = None
    
    # Current execution
    current_model: Optional[str] = None
    current_architecture: Optional[str] = None
    
    @property
    def current_item(self) -> Optional[GridItem]:
        if 0 <= self.current_index < len(self.grid):
            return self.grid[self.current_index]
        return None


class Checkpoint(BaseModel):
    """Checkpoint for resuming interrupted executions"""
    launcher_state: LauncherState
    last_run_state: Optional[RunState] = None
    saved_at: datetime = Field(default_factory=datetime.now)
    
    # Completed results summary
    completed_results: List[Dict[str, Any]] = Field(default_factory=list)


class CompletedRunSummary(BaseModel):
    """Summary of a completed run for the results table"""
    model: str
    architecture: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    score: float = 0.0
    total_questions: int = 0
    completed_at: Optional[datetime] = None
    result_file: Optional[str] = None
    
    # Métricas adicionais
    total_time: float = 0.0  # Tempo total em segundos
    tokens_per_second: float = 0.0  # Output tokens por segundo
    
    # Estatísticas por dificuldade
    easy_percentage: float = 0.0  # % de acerto em easy
    medium_percentage: float = 0.0  # % de acerto em medium
    hard_percentage: float = 0.0  # % de acerto em hard
    total_percentage: float = 0.0  # % de acerto geral (média simples)
    
    # Contadores (usando float para suportar success_rate parcial)
    easy_total: int = 0
    easy_passed: float = 0.0
    medium_total: int = 0
    medium_passed: float = 0.0
    hard_total: int = 0
    hard_passed: float = 0.0
    total_passed: float = 0.0  # Total de questões passadas (todas as dificuldades)
