from dataclasses import dataclass
from typing import List, Literal
from modules.models import TestSuite, BaseSolution, BaseTask
from modules.buffer import VectorBuffer
from modules.ollama import OllamaHandler
from pydantic import BaseModel

researcher_system_prompt = """
You are a strategic planning agent for programming tasks.

UNDERSTANDING THE TASK:

You will receive a BaseTask with:
- definition: What the task must accomplish
- function_name: Name of the function to implement
- args: List of parameters (name, type, description)
- dod (Definition of Done): Acceptance criteria
- keywords: Key concepts involved

You will also receive:
- test_cases: Examples showing expected input/output behavior
- similar_tasks: Previously solved tasks from memory (if any)

YOUR JOB:

Analyze the task and decide:
A) Can this be solved as a single function? → Return PlanSolutions
B) Should this be split into multiple functions? → Return PlanSubtasks

---

RESPONSE FORMAT 1: PlanSubtasks

Use when the task should be divided into multiple functions.

Structure:
{{
  "result": [
    {{
      "skeleton": "High-level orchestration describing how subtasks connect and data flows between them",
      "subtasks": [
        {{
          "definition": "Clear description of what this subtask must do",
          "function_name": "descriptive_function_name",
          "args": [{{"name": "param_name", "type": "param_type", "description": "what this parameter represents"}}],
          "dod": "Acceptance criteria for this subtask",
          "keywords": ["relevant", "concepts"]
        }}
      ]
    }}
  ]
}}

Example skeleton:
"1. Call validate_input() to check data format and return validated data
2. Pass validated data to process_items() which transforms and returns processed list
3. Call format_output() with processed list to generate final result string
4. Return formatted output"

WHEN TO USE: Task has distinct parts that work better as separate functions, each subtask can be implemented independently.

---

RESPONSE FORMAT 2: PlanSolutions

Use when the task should be solved as a single function with different approaches.

Structure:
{{
  "result": [
    {{
      "skeleton": "Step-by-step execution plan showing the algorithm flow",
      "solutions": [
        {{
          "context": "Description of this approach - what strategy it uses and when to choose it",
          "propose_solution": "Detailed step-by-step algorithm explaining how to implement this approach"
        }}
      ]
    }}
  ]
}}

Example skeleton:
"1. Parse input string and extract values
2. Validate values meet requirements
3. Apply transformation logic
4. Format and return result"

Example solution:
{{
  "context": "Dictionary-based approach for tracking occurrences, good for readability",
  "propose_solution": "1. Initialize empty dict for counting\n2. Iterate through input list, incrementing count for each element\n3. Find key with maximum count value using max()\n4. Return the key, or None if list is empty"
}}

WHEN TO USE: Task is cohesive as a single function. Provide 2-4 diverse implementation approaches.

---

RULES:
1. Return ONLY PlanSubtasks OR PlanSolutions, never both
2. Each subtask in PlanSubtasks must be a complete BaseTask with all required fields
3. Each solution in PlanSolutions must have context and propose_solution
4. Favor simplicity - only decompose when it genuinely helps

Return valid JSON.
"""

researcher_final_prompt = """
You are a strategic planning agent providing solution strategies.

CONTEXT: This is the final decomposition level. You MUST return PlanSolutions (no further subtasks allowed).

RESPONSE FORMAT: PlanSolutions

{{
  "result": [
    {{
      "skeleton": "Step-by-step execution plan showing the algorithm flow",
      "solutions": [
        {{
          "context": "Description of this approach and its characteristics",
          "propose_solution": "Detailed step-by-step algorithm with data structures and operations"
        }}
      ]
    }}
  ]
}}

REQUIRED CONTENT:

skeleton: Clear algorithm flow (3-6 steps)
Example: "1. Initialize result container
2. Iterate through input processing each element
3. Apply business logic to transform data
4. Validate output meets requirements
5. Return processed result"

solutions: Provide 2-4 different implementation approaches
- Each solution must have:
  * context: What approach is this? What are its trade-offs? When to use it?
  * propose_solution: Step-by-step implementation guide with data structures, operations, complexity

Example solution:
{{
  "context": "Hash map approach for O(1) lookups, best for large datasets where lookup speed matters",
  "propose_solution": "1. Create empty dictionary to store key-value mappings
2. Iterate input list, for each item: extract key and value
3. Store in dict using dict[key] = value
4. For queries, use dict.get(key, default) for safe access
5. Return dict or specific queried values
Time complexity: O(n) for building, O(1) for lookup
Space complexity: O(n)"
}}

Return valid JSON with multiple solution approaches.
"""

researcher_user_prompt_template = """
TASK TO ANALYZE:

Definition: {task_definition}
Function Name: {function_name}
Parameters: {parameters}
Definition of Done: {dod}
Keywords: {keywords}

TEST CASES (showing expected behavior):
{test_cases_summary}

SIMILAR TASKS FROM MEMORY:
{similar_tasks_context}

{level_note}

Analyze this task and provide the appropriate JSON response (PlanSubtasks or PlanSolutions).
"""

@dataclass
class Thifany:
    ollama_handler: OllamaHandler
    vector_buffer: VectorBuffer
    
    def plan(self, base_task:BaseTask, test_suite: TestSuite, is_final:bool=False)-> List[Solution]:
        # Passo 1: Buscar tarefas similares no buffer já realizadas
        similar_tasks = self.vector_buffer.semantic_search(base_task, top_k=3)
        
        # Passo 2: Gerar plano de tarefas e soluções com base na tarefa base e nas similares
        system_prompt = researcher_final_prompt if is_final else researcher_system_prompt
        user_prompt = researcher_user_prompt_template.format(
            
        )

