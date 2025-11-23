# Python stdlib
from dataclasses import dataclass, field
import json
import re
import time
from typing import Literal, Optional, List

# Modules
from modules.buffer import VectorBuffer
from modules.ollama import OllamaHandler, ChatResponse
from modules.logger import StatusContext, get_logger

# Schemas
from schemas.plan import PlanResponseModel, PlanResponse, PlanSubtasks, PlanSolutions
from schemas.task import BaseTask, Task, DefineTaskResponse
from schemas.tests import TestSuite, TestSuiteComplete, TestCase
from modules.dataloader import QuestionDataset

# Prompts
from agents.reseacher.prompt_plan import decide_plan_system_prompt, user_prompt_template_decide, user_prompt_template_base, plan_type_extract_prompt
from agents.reseacher.prompt_subtasks import system_generate_subtasks_prompt, system_extract_subtasks_prompt
from agents.reseacher.prompt_solutions import system_generate_solutions_prompt, system_extract_solutions_prompt, create_template_prompt
from agents.reseacher.prompt_question import system_extract_task_prompt, user_extract_task_template, base_code

logger = get_logger(__name__)

@dataclass
class Thifany:
    ollama_handler: OllamaHandler
    vector_buffer: VectorBuffer = field(default_factory=lambda: VectorBuffer())
    
    # PUBLIC FUNCTIONS
    
    def plan(self, base_task:BaseTask, test_suite: TestSuite, is_final:bool=False, use_buffer:bool=False)-> PlanResponse:
        # Passo 1: Buscar tarefas similares no buffer já realizadas
        with StatusContext("RESEARCHER: Searching for similar tasks in buffer.") as status:
            start_time = time.time()
            similar_tasks = self._find_similar_tasks(base_task, top_k=3) if use_buffer else "No similar tasks found."
            logger.debug(f"RESEARCHER: Similar tasks search took {time.time() - start_time:.2f} seconds.")
            
            # Passo 2: Criar prompt de usuário descrevendo a tarefa atual
            user_prompt =  user_prompt_template_base.format(
                task_definition=base_task.definition,
                function_name=base_task.function_name,
                parameters=", ".join([f"{arg.name} ({arg.type}): {arg.description or 'No description'}" for arg in base_task.args]),
                dod=base_task.dod,
                test_cases_summary=test_suite.test_cases_summary(),
                similar_tasks_context=similar_tasks
            )

            # Passo 3: Caso não seja o ramo máximo de decomposição estabelecido
            if not is_final:
                # Passo 3.1: Eviar para o agente pesquisador decidir entre subtarefas ou soluções
                plan_response = self._decide_plan_type(user_prompt)
                # Passo 3.2: Se subtarefas, usar o prompt para gerar subtarefas

                if plan_response.result_type == 'subtasks':
                    subtasks = self._plan_subtasks(user_prompt)
                    # Passo 3.3 Caso tenha pelo menos 2 subtarefas, retornar o plano de subtarefas
                    if len(subtasks.subtasks) >=2:
                        return PlanResponse(
                            reasoning=plan_response.reasoning,
                            result_type='subtasks',
                            subtasks=subtasks,
                            solutions=None
                        )

            # Passo 4: Caso seja o ramo máximo de decomposição, ou o resultado do plano seja soluções, o modelo deverá crar as soluções
            solutions = self._plan_solutions(user_prompt)
            return PlanResponse(
                reasoning="",
                result_type='solutions',
                subtasks=None,
                solutions=solutions
            )
    
    def save_history(self, task:Task)->str:
        task_dict = {
            "definition": task.definition,
            "dod": task.dod,
            "best_solution": task.best_solution,
            "best_solution_rating": task.best_solution_rating,
            "function_name": task.function_name,
            "code_snippet": task.code,
        }
        
        task_dict_str = json.dumps(task_dict, indent=2)
        
        messages = [
            {"role": "system", "content": create_template_prompt},
            {"role": "user", "content": task_dict_str}
        ]
        
        with StatusContext("RESEARCHER: Creating resolution template from task history.") as status:
            logger.debug("RESEARCHER: Sending template creation prompt to Ollama.")
            start_time = time.time()
            response = self.ollama_handler.generate_response(messages=messages)
            logger.debug(f"RESEARCHER: Template creation prompt took {time.time() - start_time:.2f} seconds.")
        
        assert isinstance(response, ChatResponse) and \
            type(response.response) == str, \
                "Response is not of type ChatResponse with string content."
        
        task.template = response.response
        
        self.vector_buffer.create(task)
        return response.response
    
    def define_task(self, question_dataset: QuestionDataset) -> Task:
        task_template = self._create_task_template(question_dataset)
        return Task(
            definition=task_template.definition,
            dod=task_template.dod,
            keywords=task_template.keywords,
            function_name="main",
            args=[],
            test_suite=self._create_test_suite(question_dataset.public_test_cases),
            template="",
            best_solution="",
            best_solution_rating=0.0,
            code=""
        )
        
    # PRIVATE FUNCTIONS
    
    @staticmethod
    def _extract_final_decision_regex(text: str) -> Optional[Literal["subtasks", "solutions"]]:
        text = text.lower()
        pattern = r'(?:final\s+decision|decision)[:\s\*]*([a-z]+)'
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        
        if matches:
            decision = matches[-1].strip().lower()
            if "subtask" in decision: return "subtasks"
            if "solution" in decision: return "solutions"
            
        return None
    
    def _decide_plan_type(self, user_prompt:str) -> PlanResponseModel:
        with StatusContext("RESEARCHER: Deciding plan type (subtasks or solutions).") as status:
            messages = [
                {"role": "system", "content": decide_plan_system_prompt},
                {"role": "user", "content": user_prompt + "\n" + user_prompt_template_decide}
            ]
            start_time = time.time()
            logger.debug("RESEARCHER: Sending plan type decision prompt to Ollama.")
            response = self.ollama_handler.generate_response(messages=messages)
            logger.debug(f"RESEARCHER: Plan type decision prompt took {time.time() - start_time:.2f} seconds.")
            
            assert isinstance(response, ChatResponse) and type(response.response) == str, \
                "Response is not of type ChatResponse with string content."

            if (final_decision := self._extract_final_decision_regex(response.response)):
                return PlanResponseModel(
                    reasoning=response.response,
                    result_type=final_decision
                )

            messages = [
                {"role": "system", "content": plan_type_extract_prompt},
                {"role": "user", "content": response.response}
            ]

            reasoning = response.response
            status.update("RESEARCHER: Extracting final decision from reasoning.")
            start_time = time.time()
            response = self.ollama_handler.generate_response(messages=messages)
            logger.debug(f"RESEARCHER: Final decision extraction took {time.time() - start_time:.2f} seconds.")
            
            assert isinstance(response, ChatResponse) and isinstance(response.response, str), \
                "Response is not of type ChatResponse with string content."

            result_type = "subtasks" if "subtasks" in response.response.lower() else "solutions"

            return PlanResponseModel(reasoning=reasoning,result_type=result_type) #type: ignore
    
    def _plan_subtasks(self, user_prompt:str) -> PlanSubtasks:
        
        with StatusContext("RESEARCHER: Planning subtasks.") as status:
            messages_cot = [
                {"role": "system", "content": system_generate_subtasks_prompt},
                {"role": "user", "content": user_prompt}
            ]
            start_time = time.time()
            logger.debug("RESEARCHER: Sending subtask planning prompt to Ollama.")
            cot_response = self.ollama_handler.generate_response(messages=messages_cot)
            assert isinstance(cot_response, ChatResponse) and \
                isinstance(cot_response.response, str), \
                    "Response is not of type ChatResponse with string content."
            logger.debug(f"RESEARCHER: Subtask planning prompt took {time.time() - start_time:.2f} seconds.")
            
            messages_subtasks = [
                {"role": "system", "content": system_extract_subtasks_prompt},
                {"role": "user", "content": cot_response.response}
            ]
            
            status.update("RESEARCHER: Extracting subtasks from reasoning.")
            logger.debug("RESEARCHER: Sending subtask extraction prompt to Ollama.")
            start_time = time.time()
            subtasks_response = self.ollama_handler.generate_response(
                messages=messages_subtasks,
                response_format=PlanSubtasks #type:ignore
            )
            logger.debug(f"RESEARCHER: Subtask extraction prompt took {time.time() - start_time:.2f} seconds.")
            
            assert isinstance(subtasks_response, ChatResponse) and \
                isinstance(subtasks_response.response, PlanSubtasks), \
                    "Response is not of type PlanSubtasks."

            return subtasks_response.response
    
    def _plan_solutions(self, user_prompt:str) -> PlanSolutions:
        with StatusContext("RESEARCHER: Planning solutions.") as status:
            messages_cot = [
                {"role": "system", "content": system_generate_solutions_prompt},
                {"role": "user", "content": user_prompt}
            ]

            logger.debug("RESEARCHER: Sending solution planning prompt to Ollama.")
            start_time = time.time()
            cot_response = self.ollama_handler.generate_response(messages=messages_cot)
            assert isinstance(cot_response, ChatResponse) and \
                isinstance(cot_response.response, str),\
                    "Response is not of type ChatResponse with string content."

            logger.debug(f"RESEARCHER: Solution planning prompt took {time.time() - start_time:.2f} seconds.")
            messages_solutions = [
                {"role": "system", "content": system_extract_solutions_prompt},
                {"role": "user", "content": cot_response.response}
            ]
            status.update("RESEARCHER: Extracting solutions from reasoning.")
            logger.debug("RESEARCHER: Sending solution extraction prompt to Ollama.")
            start_time = time.time()
            solutions_response = self.ollama_handler.generate_response(
                messages=messages_solutions,
                response_format=PlanSolutions #type:ignore
            )
            logger.debug(f"RESEARCHER: Solution extraction prompt took {time.time() - start_time:.2f} seconds.")

            assert isinstance(solutions_response, ChatResponse) and \
                isinstance(solutions_response.response, PlanSolutions), \
                    "Response is not of type PlanSolutions."

            return solutions_response.response
    
    def _find_similar_tasks(self, base_task:BaseTask, top_k:int=3) -> str:
        similar_tasks = self.vector_buffer.semantic_search(base_task, top_k=top_k)
        if not similar_tasks:
            return "No similar tasks found."
        
        context = ""
        for i, task in enumerate(similar_tasks):
            context += f"Similar Task {i+1}:\n"
            context += f"- Definition: {task.definition}\n"
            context += f"- Definition of Done: {task.dod}\n"
            context += f"- Solution Rating: {task.best_solution_rating}\n"
            context += f"- Resolution Template: {task.template}\n\n"
        
        return context
    
    def _create_task_template(self, question_dataset: QuestionDataset) -> DefineTaskResponse:
        with StatusContext("RESEARCHER: Creating task template from question dataset.") as status:
            messages = [
                {"role": "system", "content": system_extract_task_prompt},
                {"role": "user", "content": user_extract_task_template.format(
                    title=question_dataset.title,
                    content=question_dataset.content
                )}
            ]
            logger.debug("RESEARCHER: Sending task template creation prompt to Ollama.")
            start_time = time.time()
            response = self.ollama_handler.generate_response(
                messages=messages,
                response_format=DefineTaskResponse #type:ignore
            )
            logger.debug(f"RESEARCHER: Task template creation prompt took {time.time() - start_time:.2f} seconds.")
            
            assert isinstance(response, ChatResponse) and \
                isinstance(response.response, DefineTaskResponse), \
                    "Response is not of type DefineTaskResponse."

            return response.response
    
    def _create_test_suite(self, tests_cases : List[TestCase]) -> TestSuiteComplete:
        tests_cases_formatted = []
        
        for test_case in tests_cases:
            tests_cases_formatted.append(
                TestCase(
                    inputs=test_case.inputs,
                    expected_output=test_case.expected_output
                )
            )
        
        return TestSuiteComplete(
            function_name="main",
            test_cases=tests_cases_formatted,
            test_code_raw=base_code
        )