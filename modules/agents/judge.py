from dataclasses import dataclass

from pydantic import BaseModel

from modules.ollama import OllamaHandler, ChatResponse
from modules.models import Solution

judge_code_prompt_template = \
"""
You are an exceptional code analyst with deep reasoning skills and the ability to deliver precise, constructive feedback.

Your task is to evaluate whether the code provided by the user strictly follows the criteria they specify. You must:

1. Carefully read and understand the criteria provided by the user.
2. Analyze the code thoroughly to determine whether it satisfies all the criteria.
3. If the code fully satisfies the criteria, return:
   {{
     "is_correct": true,
     "feedback": "[Explain why the code is correct, highlighting the strengths and alignment with the criteria.]"
   }}

4. If the code does not satisfy the criteria, return:
   {{
     "is_correct": false,
     "feedback": "[Explain clearly what is missing, incorrect, or misinterpreted. Be specific and technical.]"
   }}

5. Your feedback must be:
   - Technically accurate and deeply reasoned
   - Focused on the user's criteria
   - Clear, concise, and actionable
   - Written in natural language (not code)

6. Do not include any code in your response.
7. Do not return anything except the JSON object matching the following structure:

```json
{{
  "is_correct": true | false,
  "feedback": "..."
}}
```
The criteria to evaluate are as follows:
{criteria}
"""

evaluate_solution_prompt_template = \
"""You are a highly analytical and rigorous evaluator of software solutions. Your role is to assess whether a proposed solution correctly and effectively solves a given challenge.

The challenge to be solved is:

{template}

Your task is to:

1. Carefully read and understand the challenge described above.
2. Analyze the user's proposed solution in depth.
3. Determine whether the solution fully and correctly addresses the challenge.
4. If the solution is valid and complete, return:
   {{
     "is_correct": true,
     "feedback": "[Explain why the solution is correct, highlighting its strengths and alignment with the challenge.]"
   }}
5. If the solution is incorrect, incomplete, or misaligned with the challenge, return:
   {{
     "is_correct": false,
     "feedback": "[Explain clearly what is wrong or missing, and why the solution does not meet the challenge requirements.]"
   }}

Guidelines for your evaluation:

- Your feedback must be technically sound, deeply reasoned, and focused on the challenge.
- Be specific and constructive in your critique.
- Do not include any code in your response.
- Do not return anything except the JSON object matching the following structure:

```json
{{
  "is_correct": true | false,
  "feedback": "..."
}}
```
"""

class CodeJudgment(BaseModel):
    is_correct: bool
    feedback: str

@dataclass
class Will:
    ollama_handler: OllamaHandler
    
    def judge_solution(self, solution: Solution) -> CodeJudgment:
        messages = [
            {"role": "system", "content": evaluate_solution_prompt_template.format(solution.problem.definition)},
            {"role": "user", "content": solution.propose_solution}
        ]
        
        response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=CodeJudgment # type:ignore
        )
        return response.response # type:ignore

    def judge_code(self, solution: Solution)->CodeJudgment:
        messages = [
            {"role": "system", "content": judge_code_prompt_template.format(
                criteria=solution.propose_solution)},
            {"role": "user", "content": solution.solution_history[-1]['content']}
        ]
        response = self.ollama_handler.generate_response(
            messages=messages,
            response_format=CodeJudgment # type:ignore
        )
        return response.response # type:ignore