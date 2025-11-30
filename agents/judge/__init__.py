from dataclasses import dataclass
import re
import time
from typing import Tuple

from pydantic import BaseModel

from modules.llm import OllamaHandler, ChatResponse
from modules.logger import get_logger, StatusContext

from schemas.solution import Solution, BaseSolution
from schemas.tests import TestSuite, TestsResult

from .prompts import (
    judge_code_system_prompt, evaluate_solution_system_prompt,
    extract_feedback_system_prompt, error_analysis_system_prompt,
    analyze_test_failures_user_template, extract_solution_system_prompt
)

feedback_pattern = r"<feedback>\s*(.*?)\s*</feedback>"
is_correct_pattern = r"<is_correct>\s*(.*?)\s*</is_correct>"
propose_solution_pattern = r"<propose_solution>\s*(.*?)\s*</propose_solution>"
context_pattern = r"<context>\s*(.*?)\s*</context>"

logger = get_logger(__name__)

class Judgment(BaseModel):
    is_correct: bool
    feedback: str

@dataclass
class Will:
    ollama_handler: OllamaHandler
    
    def judge_solution(self, solution: Solution) -> Tuple[bool, Solution]:
        messages = [
            {"role": "system", "content": evaluate_solution_system_prompt},
            {"role": "user", "content": solution.propose_solution}
        ]
        
        logger.info("Judge: Judging the proposed solution.")
        start_time = time.time()
        with StatusContext("Judge: Judging the proposed solution") as status:
            response = self.ollama_handler.chat(messages=messages)
        logger.debug(f"Judge: Judgment response generation took {time.time() - start_time:.2f} seconds.")
        
        
        analysis = self._parse_judgment_response(response.response)
        
        logger.info(f"Judge: Solution judged as {'correct' if analysis.is_correct else 'incorrect'}.")
        
        if not analysis.is_correct:
            solution.solution_history.append({"role": "judge","content": analysis.feedback})
        
        return analysis.is_correct, solution

    def judge_code(self, solution: Solution)->Tuple[bool, Solution]:
        messages = [
            {"role": "system", "content": judge_code_system_prompt.format(criteria=solution.propose_solution)},
            {"role": "user", "content": solution.solution_history[-1]['content']}
        ]
        logger.info("Judge: Judging the generated code solution.")
        start_time = time.time()
        
        with StatusContext("Judge: Judging the generated code solution") as status:
            response = self.ollama_handler.chat(messages=messages)
        logger.debug(f"Judge: Judgment response generation took {time.time() - start_time:.2f} seconds.")
        
        analysis = self._parse_judgment_response(response.response)
        
        logger.info(f"Judge: Code judged as {'correct' if analysis.is_correct else 'incorrect'}.")
        
        if not analysis.is_correct:
            solution.solution_history.append({"role": "judge","content": analysis.feedback})
        
        return analysis.is_correct, solution
    
    def analyze_test_failures(self, solution: Solution, test_suite:TestSuite, tests_results:TestsResult)->Solution:
        messages = [
            {"role": "system", "content": error_analysis_system_prompt},
            {"role" : "user", "content": analyze_test_failures_user_template.format(
                solution_context=solution.context,
                propose_solution=solution.propose_solution,
                code=tests_results.raw_code,
                test_suite_summary=test_suite.test_cases_summary(no_code=True),
                tests_report=tests_results.display_errors()
            )}
        ]
        
        logger.info("Judge: Analyzing test failures to refine the solution.")
        start_time = time.time()
        with StatusContext("Judge: Analyzing test failures to refine the solution") as status:
            response = self.ollama_handler.chat(messages=messages)
        logger.debug(f"Judge: Analyze test failures response generation took {time.time() - start_time:.2f} seconds.")
        
        solution_update = self._parse_analyze_test_failures(response.response)
        
        solution.solution_history.append({"role": "judge","content": response.response})
        solution.context = solution_update.context
        solution.propose_solution = solution_update.propose_solution
        
        return solution
    
    
    def _parse_judgment_response(self, response_text: str) -> Judgment:
        logger.debug("Judge: Parsing judgment response.")
        feedback_match = re.search(feedback_pattern, response_text, re.DOTALL | re.IGNORECASE)
        is_correct_match = re.search(is_correct_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if feedback_match and is_correct_match:
            feedback = feedback_match.group(1).strip()
            is_correct_str = is_correct_match.group(1).strip().lower()
            is_correct = is_correct_str in ["true", "correct", "pass"]
            return Judgment(is_correct=is_correct, feedback=feedback)
        
        logger.warning("Judge: Judgment response missing expected tags, using extraction model.")
        messages = [
            {"role": "system", "content": extract_feedback_system_prompt},
            {"role": "user", "content": response_text}
        ]
        
        with StatusContext("Judge: Extracting judgment feedback") as status:
            extraction_response = self.ollama_handler.chat(
                messages=messages,
                response_format=Judgment
            )
        
        # Verifica se o parse foi bem-sucedido
        if isinstance(extraction_response.response, Judgment):
            logger.debug("Judge: Successfully extracted judgment feedback.")
            return extraction_response.response
        
        # Fallback: se o parse falhou, retorna julgamento como incorreto
        logger.error("Judge: Failed to parse judgment response. Returning default incorrect judgment.")
        return Judgment(is_correct=False, feedback="Unable to parse judgment feedback from model response")
        
    def _parse_analyze_test_failures(self, response_text:str)-> BaseSolution:
        logger.debug("Judge: Parsing analyze test failures response.")
        new_context_match = re.search(context_pattern, response_text, re.DOTALL | re.IGNORECASE)
        new_propose_solution_match = re.search(propose_solution_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if new_context_match and new_propose_solution_match:
            new_context = new_context_match.group(1).strip()
            new_propose_solution = new_propose_solution_match.group(1).strip()
            return BaseSolution(context=new_context, propose_solution=new_propose_solution)
        
        logger.warning("Judge: Analyze test failures response missing expected tags.")
        
        messages = [
            {"role": "system", "content": extract_solution_system_prompt},
            {"role": "user", "content": response_text}
        ]
        
        with StatusContext("Judge: Extracting solution from analyze test failures response") as status:
            extraction_response = self.ollama_handler.chat(
                messages=messages,
                response_format=BaseSolution
            )
        
        # Verifica se o parse foi bem-sucedido
        if isinstance(extraction_response.response, BaseSolution):
            return extraction_response.response
        
        # Fallback: se o parse falhou e retornou string, cria BaseSolution vazio com o texto
        logger.error("Judge: Failed to parse analyze test failures response into BaseSolution. Using fallback.")
        return BaseSolution(
            context=response_text[:500] if response_text else "Error parsing context",
            propose_solution="Unable to extract solution from response"
        )
        