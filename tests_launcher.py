import ollama
import sys
import subprocess
from itertools import product
from modules.llm import OllamaHandler
from tqdm.auto import tqdm

available_models = [
    "gpt-oss:20b",
    "gemma3:1b", "gemma3:latest", "gemma3:12b",
    "qwen3:1.7b", "qwen3:8b", "qwen3:14b",
    "qwen2.5-coder:1.5b",  "qwen2.5-coder:7b", "qwen2.5-coder:14b",
]

architectures = ["simple", "multi-agent"]

grid = product(available_models, architectures)

for model, architecture in tqdm(grid):
    subprocess.run([sys.executable, "main.py", "--model", model, "--architeture", architecture])

    