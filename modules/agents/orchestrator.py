from typing import List

from pydantic import BaseModel, Field

from modules.agents.developer import Ellian
from modules.agents.judge import Will
from modules.agents.qa import Carlos
from modules.agents.reseacher import Thifany

from modules.buffer import VectorBuffer
from modules.schemas.task import Task, BaseTask
from modules.schemas.solution import Solution, BaseSolution
from modules.schemas.tests import TestSuiteComplete
from modules.schemas.plan import PlanResponse
from modules.ollama import OllamaHandler


class OrchestratorConfig(BaseModel):
    model: str = Field(
        ...,description="Name of the model to use for generation.")
    max_iter: int = Field(
        ..., description="Maximum number of task branching/generation iterations (controls recursion/fanout).")
    max_retry: int = Field(
        ..., description="Maximum number of consecutive attempts allowed for generating a valid solution or code block before failing.")
    dev_verbosity: int = Field(
        ..., description="Verbosity level for code output: 0 = no comments, 1 = user step as comments, 2 = comments plus technical explanations.")
    judge_level: int = Field(
        ..., description="Strictness level for the judge agent when evaluating solutions: 0=off, 1=checks if code solves the step, 2=evaluates robustness before codegen.")
    use_buffer: bool = Field(
        False, description="Enable use of vector buffer (RAG) for similar task retrieval and solution candidate enrichment."
    )
    ignore_warnings: bool = Field(
        True, description="Whether to ignore warnings during type checking and code analysis."
    )


class Vivi:
    def __init__(self, orchestrator_config: OrchestratorConfig):
        # Parâmetros de Teste
        self.model_name = orchestrator_config.model
        self.max_iter = orchestrator_config.max_iter
        self.max_retry = orchestrator_config.max_retry
        self.judge_level = orchestrator_config.judge_level
        self.use_buffer = orchestrator_config.use_buffer
        self.ignore_warnings = orchestrator_config.ignore_warnings

        # Agentes
        self.ollama_handler = OllamaHandler(
            model_name=orchestrator_config.model, temperature=0.5, keep_alive=True)
        self.dev = Ellian(
            ollama_handler=self.ollama_handler, verbosity=orchestrator_config.dev_verbosity, generation_retry_attempts=self.max_retry, ignore_warnings=self.ignore_warnings)
        self.judge = Will(
            ollama_handler=self.ollama_handler)
        self.qa = Carlos(
            ollama_handler=self.ollama_handler, retry_attempts=self.max_retry)
        self.researcher = Thifany(
            ollama_handler=self.ollama_handler, vector_buffer=VectorBuffer())

    def solve_base_task(self, base_task: BaseTask, iteration: int) -> Task:
        # O Primeiro passo é o QA Criar casos de teste para a task
        task_test_suite = self.qa.create_tests_suite(base_task)

        task = Task(test_suite=task_test_suite, **base_task.model_dump())

        # Depois vamos para a abordagem de resolver a task, se será ramificar [subtasks] ou uma abordagem de partir para as soluções
        solve_task_plan = self.researcher.plan(
            base_task, task_test_suite, iteration <= self.max_iter, self.use_buffer)

        # Caso a abordagem sugerida seja de subtasks, vamos resolver cada subtask recursivamente
        assert ((solve_task_plan.solutions is None) ^ (solve_task_plan.subtasks is None)), \
            "Either solutions or subtasks must be provided, not both"
        
        task = \
            self.solution_search(task, solve_task_plan.solutions.solutions) \
            if solve_task_plan.result_type == 'solutions' and solve_task_plan.solutions is not None \
            else self.solve_subtasks(task,solve_task_plan.subtasks,iteration -1) #type: ignore
        
        # Atualiza o template de solução
        task.template = self.researcher.save_history(task)

        return task
    
    def solve_subtasks(self, task: Task, plan_subtask:PlanResponse, iteration: int) -> Task:
        assert plan_subtask.subtasks is not None, "Subtasks must be provided for 'subtasks' plan type."
        skeleton = plan_subtask.subtasks.skeleton
        subtasks = plan_subtask.subtasks.subtasks
        
        solved_tasks = []
        for subtask in subtasks:
            solved_subtask = self.solve_base_task(subtask, iteration)
            solved_tasks.append(solved_subtask)
        
        # Depois vamos juntar as partes que foram feitas e criar o código final da task principal
        task.code = self.dev.join_subtasks_code(
            main_task=task, subtasks=solved_tasks, skeleton=skeleton)
        
        # Vamos transformar a Task em Uma solução para fazer o loop de ajustes
        
        solution = Solution(
            context=task.definition,
            propose_solution=skeleton,
            best_code=task.code,
            success_rate=0.0,
            solution_history=[{"role": "developer", "content": task.code}]
        )
        
        retries = 0
        
        while True:
            code = solution.solution_history[-1]['content']
            
            tests_result = self.qa.run_tests(task.test_suite, code)
            
            if tests_result.success_rate >= solution.success_rate:
                solution.success_rate = tests_result.success_rate
                solution.best_code = code
            
            if tests_result.success_rate == 1.0:
                break
            
            solution = self.judge.analyze_test_failures(solution, task.test_suite, tests_result)
            solution.context = task.definition
            
            if retries < self.max_retry:
                solution = self.dev.generate_solution_code(solution)
                retries += 1
                continue
            
            break
        
        task.best_solution = solution.propose_solution
        task.best_solution_rating = solution.success_rate
        task.code = solution.best_code
        
        return task

    def solve_solution(self, solution: Solution, tests_suite: TestSuiteComplete) -> Solution:
        # 1. Caso o nível do juiz seja 2, julga a solução antes de gerar o código
        if self.judge_level == 2:
            is_correct, solution = self.judge.judge_solution(solution)
        
        # 2. Gera o código para a solução
        solution = self.dev.generate_solution_code(solution)
        
        # 3. Se o nível do juiz for >= 1 o código é julgado pelo juiz
        if self.judge_level >= 1:
            is_correct, solution = self.judge.judge_code(solution)
            if not is_correct:
                solution = self.dev.generate_solution_code(solution)
        
        code = solution.solution_history[-1]['content']
        
        # 4. É feita a execução dos testes
        tests_result = self.qa.run_tests(tests_suite, code)
        
        # 5. Atualiza a taxa de sucesso da solução se for maior que a anterior
        if tests_result.success_rate >= solution.success_rate:
            solution.success_rate = tests_result.success_rate
            solution.best_code = code
        
        # 6. Se a solução obteve sucesso total nos testes, é retornada a solução.
        if tests_result.success_rate == 1.0:
            return solution
        
        # 7. Se não obteve sucesso total, o modelo juíz avalia o erro e formula os próximos passos que devem ser tomados para resolver o problema
        solution = self.judge.analyze_test_failures(solution, tests_suite, tests_result)
        
        # 8. Retorna a solução atualizada
        return solution

    def solution_search(self, task:Task, base_solutions: List[BaseSolution]) -> Task:
        # 1. Inicializa as soluções
        solutions = []
        for solution in base_solutions:
            solutions.append(Solution(**solution.model_dump()))
        
        # 2. Incializa variáveis de controle
        best_solution_rate = -1.0
        best_solution = solutions[0]
        
        # 3. Loop de tentativas
        for _ in range(self.max_retry):
            # 3.1 Ordena as soluções pela taxa de sucesso (a solução mais promissora primeiro)
            solutions = sorted(solutions, key=lambda s: s.success_rate, reverse=True)
            # 3.2 Tenta resolver cada solução
            for solution in solutions:
                solution = self.solve_solution(solution, task.test_suite)
                # 3.2.2 Atualiza a melhor solução encontrada até agora
                if solution.success_rate > best_solution_rate:
                    best_solution_rate = solution.success_rate
                    best_solution = solution
                
                # 3.2.1 Se a solução for perfeita, retorna imediatamente
                if solution.success_rate == 1.0:
                    break
            if best_solution_rate == 1.0:
                break
        
        task.best_solution = best_solution.propose_solution
        task.best_solution_rating = best_solution.success_rate
        task.code = best_solution.best_code
        
        return task