"""
Configuration loading utilities for TUI.
"""
from pathlib import Path
from typing import Dict, Any, List, Tuple

import yaml


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Carrega configuração do arquivo YAML.
    
    Args:
        config_path: Caminho para o arquivo de configuração
        
    Returns:
        Dict com configurações ou dict vazio se falhar
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_benchmark_grid(config: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Gera lista de combinações (modelo, arquitetura) do config.
    
    Exclui modelos "cloud" de multi-agent automaticamente.
    
    Args:
        config: Configuração carregada
        
    Returns:
        Lista de tuplas (modelo, arquitetura)
    """
    models_config = config.get("benchmark", {}).get("models", {})
    architectures = config.get("benchmark", {}).get("architectures", ["simple"])
    
    # Gera lista de modelos no formato "modelo:param"
    models = []
    for model_name, params in models_config.items():
        for param in params:
            models.append(f"{model_name}:{param}")
    
    # Gera combinações excluindo cloud de multi-agent
    grid = []
    for model in models:
        for arch in architectures:
            # Modelos "cloud" NUNCA rodam em multi-agent
            if "cloud" in model.lower() and arch == "multi-agent":
                continue
            grid.append((model, arch))
    
    return grid


def get_expected_questions(config: Dict[str, Any]) -> int:
    """
    Retorna número esperado de questões por run.
    
    Args:
        config: Configuração carregada
        
    Returns:
        Total de questões esperadas
    """
    ds_cfg = config.get("dataset", {})
    return (
        ds_cfg.get("easy_samples", 30) + 
        ds_cfg.get("medium_samples", 30) + 
        ds_cfg.get("hard_samples", 30)
    )


def get_paths(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Extrai caminhos do config.
    
    Args:
        config: Configuração carregada
        
    Returns:
        Dict com results_dir e dataset_file
    """
    paths = config.get("paths", {})
    return {
        "results_dir": paths.get("results", "./results/"),
        "dataset_file": paths.get("dataset_file", "./data/dataset.jsonl"),
    }
