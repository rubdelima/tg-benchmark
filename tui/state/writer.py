"""
TUI State Writer - Escreve estado para comunicação com TUI.
Usado pelo benchmark.py para atualizar o estado em tempo real.

Este módulo é importado pelo benchmark.py para escrever o estado
que a TUI (executando em outro processo) irá ler.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class TUIStateWriter:
    """
    Escreve arquivos de estado para a TUI monitorar.
    Formato compatível com tui/state/models.py
    """
    
    STATE_DIR = ".tui_state"
    RUN_STATE_FILE = "run_state.json"
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.state_dir = self.base_path / self.STATE_DIR
        self.state_dir.mkdir(exist_ok=True)
        
        # Estado atual
        self._model: str = ""
        self._architecture: str = ""
        self._status: str = "idle"
        self._started_at: Optional[datetime] = None
        self._total_questions: int = 0
        self._completed_questions: int = 0
        self._current_question: Optional[Dict[str, Any]] = None
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._results: List[Dict[str, Any]] = []
    
    @property
    def run_state_path(self) -> Path:
        return self.state_dir / self.RUN_STATE_FILE
    
    def _write_state(self) -> None:
        """Escreve o estado atual para o arquivo JSON"""
        state = {
            "model": self._model,
            "architecture": self._architecture,
            "status": self._status,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "total_questions": self._total_questions,
            "completed_questions": self._completed_questions,
            "current_question": self._current_question,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "current_score": self._calculate_score(),
            "results": self._results,
        }
        
        try:
            with open(self.run_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception:
            pass  # Silently fail - TUI state is optional
    
    def _calculate_score(self) -> float:
        """Calcula score ponderado"""
        if not self._results:
            return 0.0
        
        weights = {"easy": 1, "medium": 3, "hard": 5}
        total_weighted = 0.0
        total_weight = 0.0
        
        for r in self._results:
            weight = weights.get(r.get("difficulty", "medium"), 1)
            total_weighted += r.get("success_rate", 0) * weight
            total_weight += weight
        
        return (total_weighted / total_weight * 100) if total_weight > 0 else 0.0
    
    def start_run(
        self,
        model: str,
        architecture: str,
        total_questions: int,
        resumed_results: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Inicia uma nova execução, opcionalmente com resultados recuperados do checkpoint."""
        self._model = model
        self._architecture = architecture
        self._status = "loading_model"
        self._started_at = datetime.now()
        self._total_questions = total_questions
        self._current_question = None
        
        # Se tiver resultados do checkpoint, usa eles
        if resumed_results:
            self._results = []
            for r in resumed_results:
                self._results.append({
                    "question_id": r.get("question_id", ""),
                    "difficulty": r.get("difficulty", "unknown"),
                    "total_time": r.get("total_time", 0.0),
                    "passed_tests": r.get("passed_tests", 0),
                    "total_tests": r.get("total_tests", 0),
                    "success_rate": r.get("success_rate", 0.0),
                    "code_generation_time": r.get("code_generation_time", 0.0),
                    "input_tokens": r.get("total_input_tokens", 0),
                    "output_tokens": r.get("total_output_tokens", 0),
                    "error": r.get("error"),
                })
            self._completed_questions = len(self._results)
            self._total_input_tokens = sum(r.get("input_tokens", 0) for r in self._results)
            self._total_output_tokens = sum(r.get("output_tokens", 0) for r in self._results)
        else:
            self._completed_questions = 0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._results = []
        
        self._write_state()
    
    def model_loaded(self) -> None:
        """Modelo carregado com sucesso"""
        self._status = "generating_code"
        self._write_state()
    
    def start_question(
        self,
        question_id: str,
        difficulty: str,
        index: int,
        total: int,
    ) -> None:
        """Inicia processamento de uma questão"""
        self._status = "generating_code"
        self._current_question = {
            "question_id": question_id,
            "difficulty": difficulty,
            "title": question_id,
            "index": index,
            "total": total,
            "status": "generating_code",
            "started_at": datetime.now().isoformat(),
            "input_tokens": 0,
            "output_tokens": 0,
            "current_test": 0,
            "total_tests": 0,
            "passed_tests": 0,
        }
        self._write_state()
    
    def update_question_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Atualiza tokens da questão atual (após geração de código)"""
        if self._current_question:
            self._current_question["input_tokens"] = input_tokens
            self._current_question["output_tokens"] = output_tokens
            self._write_state()
    
    def start_tests(self, total_tests: int) -> None:
        """Iniciando execução de testes"""
        self._status = "running_tests"
        if self._current_question:
            self._current_question["status"] = "running_tests"
            self._current_question["total_tests"] = total_tests
            self._write_state()
    
    def finish_question(self, result: Dict[str, Any]) -> None:
        """Finaliza uma questão e adiciona resultado"""
        question_result = {
            "question_id": result.get("question_id", ""),
            "difficulty": result.get("difficulty", "unknown"),
            "total_time": result.get("total_time", 0.0),
            "passed_tests": result.get("passed_tests", 0),
            "total_tests": result.get("total_tests", 0),
            "success_rate": result.get("success_rate", 0.0),
            "code_generation_time": result.get("code_generation_time", 0.0),
            "input_tokens": result.get("total_input_tokens", 0),
            "output_tokens": result.get("total_output_tokens", 0),
            "error": result.get("error"),
        }
        
        self._results.append(question_result)
        self._completed_questions += 1
        self._total_input_tokens += question_result["input_tokens"]
        self._total_output_tokens += question_result["output_tokens"]
        self._current_question = None
        self._write_state()
    
    def finish_run(self, success: bool = True) -> None:
        """Finaliza a execução"""
        self._status = "completed" if success else "error"
        self._current_question = None
        self._write_state()
    
    def set_error(self, error: str) -> None:
        """Define estado de erro"""
        self._status = "error"
        self._write_state()
    
    def clear(self) -> None:
        """Limpa o arquivo de estado"""
        try:
            if self.run_state_path.exists():
                self.run_state_path.unlink()
        except Exception:
            pass


# Singleton global para uso no benchmark
_writer: Optional[TUIStateWriter] = None


def get_tui_writer() -> TUIStateWriter:
    """Retorna instância singleton do writer"""
    global _writer
    if _writer is None:
        _writer = TUIStateWriter()
    return _writer
