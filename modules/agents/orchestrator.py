from typing import Literal

from dataclasses import dataclass

from modules.models import BaseTask,Task, Solution
from modules.ollama import OllamaHandler


class Vivi:
    def __init__(self, model, max_iter, max_retry, dev_verbosity, judge_level, controller_model, solution_search_algorithm:Literal["bfs", "dfs", "greedy"]="bfs"):
        self.max_iter = max_iter
        self.max_retry = max_retry

    def create_task(self, input_raw)->Task:
    def decompose_task(self, task:) -> Task: ...
    def merge_task(self, task_tree): ...
    def solve_task(self, task, max_iter): ...