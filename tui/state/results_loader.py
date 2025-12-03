"""
Results loading and statistics calculation.
Loads completed runs from results directory.
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
from threading import Lock

from .models import CompletedRunSummary
from ..data import DatasetLoader, calculate_difficulty_stats, calculate_weighted_score, load_results_file


class ResultsLoader:
    """
    Carrega e processa resultados de arquivos JSON.
    """
    
    def __init__(self, results_dir: Path, dataset_loader: DatasetLoader):
        self.results_dir = results_dir
        self.dataset_loader = dataset_loader
        self._lock = Lock()
        self._completed_runs: List[CompletedRunSummary] = []
    
    def load_all(self) -> List[CompletedRunSummary]:
        """
        Carrega todos os resultados do diretório.
        
        Returns:
            Lista de CompletedRunSummary
        """
        completed = []
        
        if not self.results_dir.exists():
            return completed
        
        for result_file in self.results_dir.glob("*.json"):
            summary = self._load_result_file(result_file)
            if summary:
                completed.append(summary)
        
        with self._lock:
            self._completed_runs = completed
        
        return completed
    
    def _load_result_file(self, file_path: Path) -> Optional[CompletedRunSummary]:
        """
        Carrega um arquivo de resultado e cria um CompletedRunSummary.
        
        Args:
            file_path: Caminho para o arquivo JSON
            
        Returns:
            CompletedRunSummary ou None se falhar
        """
        data = load_results_file(file_path)
        if not data:
            return None
        
        try:
            results = data.get("results", [])
            
            # Calcula estatísticas usando o DatasetLoader
            difficulty_stats = calculate_difficulty_stats(
                results, 
                self.dataset_loader
            )
            
            # Calcula score ponderado
            score = calculate_weighted_score(difficulty_stats)
            
            # Calcula tokens totais
            total_in = sum(r.get("total_input_tokens", 0) for r in results)
            total_out = sum(r.get("total_output_tokens", 0) for r in results)
            
            # Tempo total
            total_time = sum(r.get("total_time", 0.0) for r in results)
            tokens_per_second = total_out / total_time if total_time > 0 else 0.0
            
            # Extrai estatísticas
            easy_stats = difficulty_stats.get("easy", {})
            medium_stats = difficulty_stats.get("medium", {})
            hard_stats = difficulty_stats.get("hard", {})
            total_stats = difficulty_stats.get("total", {})
            
            return CompletedRunSummary(
                model=data.get("model", "unknown"),
                architecture=data.get("architecture", "unknown"),
                total_input_tokens=total_in,
                total_output_tokens=total_out,
                score=score,
                total_questions=len(results),
                result_file=str(file_path),
                total_time=total_time,
                tokens_per_second=tokens_per_second,
                easy_percentage=easy_stats.get("percentage", 0.0),
                medium_percentage=medium_stats.get("percentage", 0.0),
                hard_percentage=hard_stats.get("percentage", 0.0),
                total_percentage=total_stats.get("percentage", 0.0),
                easy_total=easy_stats.get("total", 0),
                easy_passed=easy_stats.get("passed", 0),
                medium_total=medium_stats.get("total", 0),
                medium_passed=medium_stats.get("passed", 0),
                hard_total=hard_stats.get("total", 0),
                hard_passed=hard_stats.get("passed", 0),
                total_passed=total_stats.get("passed", 0),
            )
        except Exception:
            return None
    
    @property
    def completed_runs(self) -> List[CompletedRunSummary]:
        """Retorna cópia dos resultados carregados"""
        with self._lock:
            return self._completed_runs.copy()
