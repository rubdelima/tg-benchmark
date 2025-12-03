#!/usr/bin/env python3
"""
TG-Benchmark - Executa benchmarks de modelos LLM.

Uso:
    python main.py                     # Todos os modelos do config.yaml
    python main.py --model gemma3:1b   # Modelo específico
    python main.py --arch simple       # Arquitetura específica
    python main.py --no-resume         # Ignorar checkpoints
"""
import argparse
import json
import sys
from pathlib import Path
from itertools import product
from typing import List, Dict, Any, Tuple, Optional

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from modules.logger import get_logger
from modules.benchmark import run_single_benchmark
from modules.checkpoint import get_result_path

logger = get_logger(__name__)
console = Console()


def is_benchmark_complete(result_path: Path, expected_total: int) -> bool:
    """Verifica se um benchmark está completo (todas as questões resolvidas)."""
    if not result_path.exists():
        return False
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", [])
        return len(results) >= expected_total
    except:
        return False


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Carrega configuração YAML."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_models_list(config: Dict[str, Any]) -> List[str]:
    """Converte estrutura de models para lista de 'modelo:parametro'."""
    models_config = config.get("benchmark", {}).get("models", {})
    models = []
    for model_name, params in models_config.items():
        for param in params:
            models.append(f"{model_name}:{param}")
    return models


def get_grid(config: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Gera grid modelo x arquitetura.
    
    Nota: Modelos com "cloud" no nome do parâmetro só rodam em "simple",
    pois usam APIs externas que não suportam o fluxo multi-agent.
    """
    models = get_models_list(config)
    archs = config.get("benchmark", {}).get("architectures", ["simple"])
    
    grid = []
    for model in models:
        for arch in archs:
            # Modelos "cloud" NUNCA rodam em multi-agent
            if "cloud" in model.lower() and arch == "multi-agent":
                continue
            grid.append((model, arch))
    
    return grid


def run_grid(
    config: Dict[str, Any],
    models: Optional[List[str]] = None,
    archs: Optional[List[str]] = None,
    resume: bool = True,
) -> List[Dict[str, Any]]:
    """Executa grid de benchmarks."""
    grid = get_grid(config)
    if models:
        grid = [(m, a) for m, a in grid if m in models]
    if archs:
        grid = [(m, a) for m, a in grid if a in archs]
    
    paths = config.get("paths", {})
    results_dir = paths.get("results", "./results/")
    
    # Calcula total esperado de questões
    ds_cfg = config.get("dataset", {})
    expected_total = ds_cfg.get("easy_samples", 30) + ds_cfg.get("medium_samples", 30) + ds_cfg.get("hard_samples", 30)
    
    # Filtrar pendentes - verifica se está COMPLETO, não só se existe
    pending = []
    for m, a in grid:
        result_path = get_result_path(m, a, results_dir)
        if not resume or not is_benchmark_complete(result_path, expected_total):
            pending.append((m, a))
    
    total, done = len(grid), len(grid) - len(pending)
    
    console.print(Panel(
        f"Total: {total} | Concluídas: {done} | Pendentes: {len(pending)}",
        title="🚀 TG-Benchmark", border_style="cyan"
    ))
    
    if not pending:
        rprint("[green]✓ Todas já executadas![/green]")
        return []
    
    results = []
    for idx, (model, arch) in enumerate(pending):
        console.print(Panel(f"[bold]{model}[/bold] • {arch}", title=f"📦 {done+idx+1}/{total}", border_style="blue"))
        
        try:
            r = run_single_benchmark(model, arch, config, resume=resume)
            results.append(r)
            rprint(f"  [green]Score: {r['score']:.1f}%[/green] | {r['total_test_time']:.0f}s")
        except Exception as e:
            logger.error(f"Erro {model}/{arch}: {e}")
            rprint(f"[red]❌ {e}[/red]")
    
    # Tabela final
    if results:
        t = Table(title="📊 Resultados")
        t.add_column("Modelo", style="cyan")
        t.add_column("Arch", style="magenta")
        t.add_column("Score", justify="right", style="green")
        for r in results:
            t.add_row(r["model"], r["architecture"], f"{r['score']:.1f}%")
        console.print(t)
    
    rprint(f"\n[green]🎉 {len(results)} execuções concluídas![/green]")
    return results


def main():
    p = argparse.ArgumentParser(description="TG-Benchmark")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--model", nargs="+", help="Modelo(s) específico(s)")
    p.add_argument("--arch", nargs="+", choices=["simple", "multi-agent"])
    p.add_argument("--no-resume", action="store_true")
    args = p.parse_args()
    
    try:
        config = load_config(args.config)
    except Exception as e:
        rprint(f"[red]Erro config: {e}[/red]")
        sys.exit(1)
    
    try:
        run_grid(config, args.model, args.arch, not args.no_resume)
    except KeyboardInterrupt:
        rprint("\n[yellow]⚠️ Interrompido[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Erro: {e}")
        rprint(f"[red]❌ {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
