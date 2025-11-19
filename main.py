from modules.models import Problem
from modules.buffer import VectorBuffer
import time
from rich import print

if __name__ == "__main__":
    from dataclasses import asdict

    p1 = Problem(
        status="completed",
        definition="Reverse a list of strings.",
        keywords=["reverse", "list", "strings"],
        dod="Return a list with the order and content of each string reversed."
    )
    vb = VectorBuffer()
    idx1 = vb.create(p1)

    # Consultando por similaridade
    query_p = Problem(
        status="running",
        definition="Invert a list and invert each string in it.",
        keywords=["invert", "reverse", "list", "strings"],
        dod="Output list should have reversed order and each string reversed."
    )
    start_time = time.time()
    results = vb.semantic_search(query_p)
    end_time = time.time()
    print(f"Foram encontrados {len(results)} problemas similares em {end_time - start_time:.4f} segundos:")
    for r in results:
        
        print(r.model_dump)