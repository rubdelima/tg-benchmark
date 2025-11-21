from dataclasses import dataclass
from modules.models import *
from modules.buffer import VectorBuffer
from modules.ollama import OllamaHandler, ChatResponse
import re
import json

user_task_input = """
- Definition: Clear description of what the task must accomplish, in practical terms.
- Function Name: The name of the function that represents the purpose of the task.
- Parameters: List of all required parameters, including each parameter's name, type (e.g., str, int, list, dict), and a brief description of its role or expected content.
- Definition of Done: Exact acceptance criteria—what conditions or output must be met for the task to be considered successfully completed.
- TEST CASES: Example input(s) and output(s) illustrating expected behavior; serves to clarify requirements and edge cases for the solution.
- SIMILAR TASKS FROM MEMORY: For each similar task, include:
    - Definition: Brief overview of the previously solved problem.
    - Definition of Done: Its corresponding acceptance criteria.
    - Solution Rating: A float between 0.0 (failed all tests) and 1.0 (passed all tests); indicates how robust and correct the solution approach was. If rating is low (e.g., < 0.5), treat such solutions as warnings/examples to avoid; if high, they may be used as positive design references.
    - Resolution Template: A brief summary (or pseudocode description) of the approach and algorithm used for that similar task—not necessarily the exact code.
"""

decide_plan_system_prompt = """
You are an expert agent for analyzing and structuring Python programming tasks.

# USER TASK INPUT:
""" + user_task_input + """
# INSTRUCTION:
Reflect deeply on the above task using the following 5 numbered and detailed reasoning steps:

1. Understanding: Paraphrase the main goal and expected outcome of the task.
2. Complexity: Identify and describe the key logic blocks involved and clarify why each is, or is not, complex.
3. Flow and dependencies: Explain how different steps interact and whether there are critical dependencies.
4. Potential subtasks: Indicate which operations are complex enough for separation as subtasks and explain why. Do NOT split trivial operations.
5. Decision:
   - If there are at least two complex (not trivial) logic blocks justifying independent functions, return result_type: "subtasks".
   - Otherwise, return result_type: "solutions".

After your detailed reasoning, finish your response with:
FINAL DECISION: subtasks
or
FINAL DECISION: solutions

# OUTPUT EXAMPLES

## Example 1
1. Understanding: The task processes a large CSV of financial transactions, requiring robust validation and customer/month aggregation for reporting.
2. Complexity: Two major logic blocks—validation (handling bad formats, missing fields) and report aggregation (analysis and grouping)—both are genuinely complex.
3. Flow and dependencies: Validation must precede aggregation because bad data corrupts analytics; the validator's output becomes input for the aggregator.
4. Potential subtasks: Both validation and aggregation warrant independent functions for clarity, maintainability, and testing; basic CSV reading does not.
5. Decision: With these two justified complex blocks, I return 'subtasks'

FINAL DECISION: subtasks

## Example 2
1. Understanding: This task validates CSV rows for field presence and format.
2. Complexity: All checks (field presence, type, fix missing data) occur sequentially, forming one main logic block.
3. Flow and dependencies: Each row is validated independently; no multi-phase dependencies.
4. Potential subtasks: None are complex enough for separate functions—validation can be unified.
5. Decision: All required logic is straightforward and unified, so I return 'solutions'

FINAL DECISION: solutions
"""

user_prompt_template_base = """
TASK TO ANALYZE:

DEFINITION: 
{task_definition}

FUNCTION NAME: {function_name}

PARAMETERS:
{parameters}

DEFINITION OF DONE:
{dod}

TEST CASES:
{test_cases_summary}

SIMILAR TASKS FROM MEMORY:
{similar_tasks_context}

"""

user_prompt_template_decide = """
INSTRUCTION:
Carefully analyze all fields above and apply the 5-step reasoning process. Use similar tasks for inspiration only if Solution Rating is high; avoid low-rated approaches and explain their limitations if referenced. Return your output as a JSON with your detailed reasoning and plan type decision.
"""

plan_type_extract_prompt = (
    "Look for the last occurrence of 'FINAL DECISION:' in the text below "
    "and answer only with one word: subtasks or solutions, all lowercase. "
    "If not found, default to 'solutions'."
)

system_generate_subtasks_prompt = """
You are an expert agent specializing in decomposing complex tasks into a clear, justified sequence of subtasks.

## 1. User Input Explanation

""" + user_task_input + """

## 2. Reasoning Process

Apply these steps as your chain of thought:
- Verbally analyze the problem, arguing in detail about each logical block.
- For every decision, explain why you propose a subtask for that step. Never create subtasks for trivial actions.
- For each candidate subtask:
    - Define what the subtask does (mission/problem).
    - State criteria for successful completion (Definition of Done).
    - Assign a clear, descriptive function name.
    - List full parameter info: name, type, description.
- After listing and justifying the subtasks, organize a “skeleton”: a numbered overview showing how the main function flows, where each subtask is called, and where trivial steps appear inline.

## 3. Few-Shot Example

### USER INPUT

DEFINITION:
Process a list of sales transactions to generate, for each region, a validated summary of total sales by product.

FUNCTION NAME:
process_sales_data

PARAMETERS:
transactions (list[dict]): Each record contains 'transaction_id', 'product', 'region', 'quantity', 'price'.

DEFINITION OF DONE:
Returns a dictionary mapping region names to a dict mapping product names to their total validated sales.

TEST CASES:
Input:
[
    {"transaction_id": "T1", "product": "A", "region": "North", "quantity": 10, "price": 2.5},
    {"transaction_id": "T2", "product": "A", "region": "North", "quantity": "", "price": 2.5},
    {"transaction_id": "T3", "product": "B", "region": "South", "quantity": 5, "price": 1.8}
]
Expected Output:
{
  "North": {"A": 25.0},
  "South": {"B": 9.0}
}

SIMILAR TASKS FROM MEMORY:
None

### EXPECTED OUTPUT — REASONED STEPS AND SUBTASKS

1. The task requires ensuring that every sale record is complete and correctly formatted, then grouping validated sales per region and product to compute totals.
2. I will NOT create subtasks for loading data or simple iteration; those are trivial.
3. There are two genuine complex subtasks:
   - (a) validate_sales_records: Checks each transaction for required fields and types, omits any invalid record.
   - (b) aggregate_sales_by_region_product: Groups valid records by region and product, calculating their total sales.
4. Each complex subtask needs a precise definition of done and parameter description:
   - validate_sales_records:
     Mission: Validate fields/values; return only valid sales.
     Definition of Done: All records have correct types; invalid omitted.
     Function name: validate_sales_records
     Parameters:
        - transactions
            - type: list[dict]
            - description: input records to validate.
   - aggregate_sales_by_region_product:
     Mission: Group validated sales and sum totals by region/product.
     Definition of Done: Dict structure as expected (region → product → total).
     Function name: aggregate_sales_by_region_product
     Parameters:
        - valid_sales
            - type: list[dict]
            - description: records that passed validation.
5. Skeleton:
   1. Receive 'transactions'.
   2. Call validate_sales_records(transactions) to produce 'valid_sales'.
   3. Call aggregate_sales_by_region_product(valid_sales) for the summary.
   4. Return final result.

SUBTASKS:
- validate_sales_records
- aggregate_sales_by_region_product
"""

system_extract_subtasks_prompt ="""
You will receive a full chain-of-thought reasoning about a complex task, including the breakdown of justified subtasks, their details, and the execution skeleton.  
Your job is to **extract and output the subtasks, their complete details, and the execution skeleton as a single valid JSON object**.

## Expected JSON output format:

{
  "skeleton": "Text describing the main execution steps and where each subtask is called.",
  "subtasks": [
    {
      "function_name": "...",
      "definition": "...",
      "dod": "...",
      "args": [
        {"name": "...", "type": "...", "description": "..."}
      ]
    },
    {...}
  ]
}

## Few-Shot Example

### INPUT (reasoning steps):

1. The task requires ensuring that every sale record is complete and correctly formatted, then grouping validated sales per region and product to compute totals.
2. I will NOT create subtasks for loading data or simple iteration; those are trivial.
3. There are two genuine complex subtasks:
   - (a) validate_sales_records: Checks each transaction for required fields and types, omits any invalid record.
   - (b) aggregate_sales_by_region_product: Groups valid records by region and product, calculating their total sales.
4. Each complex subtask needs a precise definition of done and parameter description:
   - validate_sales_records:
     Mission: Validate fields and values; return only valid sales.
     Definition of Done: All records have correct types; invalid omitted.
     Function name: validate_sales_records
     Parameters:
        - transactions
            - type: list[dict]
            - description: input records to validate.
   - aggregate_sales_by_region_product:
     Mission: Group validated sales and sum totals by region/product.
     Definition of Done: Dict structure as expected (region → product → total).
     Function name: aggregate_sales_by_region_product
     Parameters:
        - valid_sales
            - type: list[dict]
            - description: records that passed validation.
5. Skeleton:
   1. Receive 'transactions'.
   2. Call validate_sales_records(transactions) to produce 'valid_sales'.
   3. Call aggregate_sales_by_region_product(valid_sales) for the summary.
   4. Return final result.

SUBTASKS:
- validate_sales_records
- aggregate_sales_by_region_product

### EXPECTED OUTPUT (valid JSON):

{
  "skeleton": "1. Receive 'transactions'. 2. Call validate_sales_records(transactions) to produce 'valid_sales'. 3. Call aggregate_sales_by_region_product(valid_sales) for the summary. 4. Return final result.",
  "subtasks": [
    {
      "function_name": "validate_sales_records",
      "definition": "Checks each transaction for required fields and correct types, omits any invalid or incomplete record.",
      "dod": "Returns a list with only valid records, all fields in correct types, invalid records omitted.",
      "args": [
        {"name": "transactions", "type": "list[dict]", "description": "Input records to validate."}
      ]
    },
    {
      "function_name": "aggregate_sales_by_region_product",
      "definition": "Groups valid sales records by region and product and calculates their total sales.",
      "dod": "Returns a dictionary mapping region names to product sales totals, correctly grouped and summed.",
      "args": [
        {"name": "valid_sales", "type": "list[dict]", "description": "Validated sales records that passed all checks."}
      ]
    }
  ]
}

---

Return only valid JSON for any new input in the same format. Do not include any commentary, reasoning, or extra text.
"""

system_generate_solutions_prompt = """
You are an expert agent specializing in planning approaches to fully solve programming tasks.
You will always receive a single task description, with these fields (never more than one task at a time):

""" + user_task_input + """

**Your job is:**
- Carefully read and understand the task in context.
- Propose one or more alternative, complete solution strategies (NOT code), each with:
    - `context`: one or two sentences explaining the key idea/benefit/context of this approach.
    - `propose_solution`: a step-by-step plan (in clear written steps, not code) covering all actions needed to reach the goal.

Guidelines:
- If only one robust approach is reasonable, provide just one on the list.
- Each solution should independently be enough for a code generator to implement the whole function for the task.

**Few-shot Example**

### USER INPUT:
DEFINITION: You receive a list of dictionaries with user records, and must return a list containing just the 'email' field for those where 'verified' is True.
FUNCTION NAME: get_verified_emails
PARAMETERS: users (list[dict]): each dict has 'email' and 'verified: bool'.
DEFINITION OF DONE: Output is list of emails of all verified users.
TEST CASES: Input: [{"email": "a@x.com", "verified": True}, {"email": "b@x.com", "verified": False}]
Expected: ["a@x.com"]

SIMILAR TASKS FROM MEMORY: None

### EXPECTED OUTPUT (structured reasoning):

Solution 1 context: For small lists, a simple loop is readable and efficient.
Proposed steps:
1. Initialize an empty output list.
2. Iterate through each user in users.
3. If 'verified' is True, append their 'email' to the list.
4. Return the list.

Solution 2 context: Using a list comprehension is concise and very “Pythonic”, good for clarity and performance in typical cases.
Proposed steps:
1. Use a list comprehension to include the 'email' from any user whose 'verified' field is True.
2. Return the resulting list.

---

Return as many solution options as make sense, each for the full original task, not for intermediate steps.
Do not output code, only stepwise plans and the context/benefit of each strategy.
"""

system_extract_solutions_prompt = """
You will receive a structured text describing one or more full solution approaches for a single programming task.  
Each approach includes:
- a brief context sentence (explaining the motivation or best scenario for using that approach)
- a clear, numbered or stepwise plan (description, in text, not code) covering all actions needed to solve the task from start to finish

Your job is to extract each solution and return the following JSON structure:

{
  "solutions": [
    {
      "context": "...",
      "propose_solution": "Step-by-step description for this complete approach."
    },
    {...}
  ]
}

## Few-Shot Example

### INPUT:

Solution 1 context: For small lists, a simple loop is readable and efficient.
Proposed steps:
1. Initialize an empty output list.
2. Iterate through each user in users.
3. If 'verified' is True, append their 'email' to the list.
4. Return the list.

Solution 2 context: Using a list comprehension is concise and very “Pythonic”, good for clarity and performance in typical cases.
Proposed steps:
1. Use a list comprehension to include the 'email' from any user whose 'verified' field is True.
2. Return the resulting list.

### EXPECTED OUTPUT:

{
  "solutions": [
    {
      "context": "For small lists, a simple loop is readable and efficient.",
      "propose_solution": "1. Initialize an empty output list. 2. Iterate through each user in users. 3. If 'verified' is True, append their 'email' to the list. 4. Return the list."
    },
    {
      "context": "Using a list comprehension is concise and very “Pythonic”, good for clarity and performance in typical cases.",
      "propose_solution": "1. Use a list comprehension to include the 'email' from any user whose 'verified' field is True. 2. Return the resulting list."
    }
  ]
}

---

Return only valid JSON exactly in this format for any new input.  
Do not include any other explanation or commentary.
"""

create_template_prompt = """
You are an expert code reviewer and problem-solver.
You will receive a JSON with all the details of a programming task, including the main problem, the final working code, summary of solution attempts ("history"), best_solution description, and rating.

Your task:
- Write a direct, numbered, step-by-step template describing exactly how the problem was solved, as learned from the final code and solution process.
- Summarize each logical step the final code used to reach the answer, in order.
- Do NOT copy or reference code directly; just describe what the code did.
- Use only concise, concrete language so another engineer can follow your solution plan and re-implement it.
- Use input data and context as needed to clarify the reasoning or key decision-points.

**IGNORE function names, arguments, code snippets, and unrelated details. Your focus is: How was this solved, step by step?**

### FEW-SHOT EXAMPLE

INPUT:

{
  "definition": "Sum all sales values grouped by category, ignoring any entries missing necessary fields.",
  "dod": "A dictionary mapping each category to its total sales value. Discard incomplete records.",
  "best_solution": "Removed all entries without both 'category' and 'amount', looped over the rest and summed sales per category.",
  "best_solution_rating": 1.0,
  "code": "valid = [x for x in data if 'category' in x and 'amount' in x]\n... # group and sum ...",
  "history": [
    {"message": "Failed: tried to sum without filtering; error due to missing fields."},
    {"message": "Success: filtered, then grouped and summed; all tests green."}
  ]
}

EXPECTED OUTPUT:

1. Remove any data items that do not have both required fields: 'category' and 'amount'.
2. For the filtered data, group entries by 'category'.
3. Add up the sales amounts for each group.
4. Output a mapping of each category to its summed sales value.

---

Return only the explicit step-by-step plan for solving this problem, based on the final code and solution history.
"""

@dataclass
class Thifany:
    ollama_handler: OllamaHandler
    vector_buffer: VectorBuffer
    
    @staticmethod
    def _extract_final_decision(response_text: str) -> Literal["subtasks", "solutions"] | None:
        response_text = response_text.lower()
        pattern = r'final decision[:\s]*([a-z]+)'
        matches = re.findall(pattern, response_text, flags=re.IGNORECASE)
        if not matches:
            return None
        decision = matches[-1].lower()
        if decision in {"subtasks", "solutions"}:
            return decision
        return None
    
    def _decide_plan_type(self, user_prompt:str) -> PlanResponseModel:
        messages = [
            {"role": "system", "content": decide_plan_system_prompt},
            {"role": "user", "content": user_prompt + user_prompt_template_decide}
        ]
        
        response = self.ollama_handler.generate_response(messages=messages)
        assert isinstance(response, ChatResponse) and isinstance(response.response, str), "Response is not of type ChatResponse with string content."
        
        if "FINAL DECISION" in response.response:
            final_decision = self._extract_final_decision(response.response)
            
            if final_decision:
                return PlanResponseModel(
                    reasoning=response.response,
                    result_type=final_decision
                )
        
        messages = [
            {"role": "system", "content": plan_type_extract_prompt},
            {"role": "user", "content": response.response}
        ]
        
        reasoning = response.response
        response = self.ollama_handler.generate_response(messages=messages)
        assert isinstance(response, ChatResponse) and isinstance(response.response, str), "Response is not of type ChatResponse with string content."
        
        result_type = "subtasks" if "subtasks" in response.response.lower() else "solutions"
        
        return PlanResponseModel(
            reasoning=reasoning,
            result_type=result_type
        )
    
    def _plan_subtasks(self, user_prompt:str) -> PlanSubtasks:
        messages_cot = [
            {"role": "system", "content": system_generate_subtasks_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        cot_response = self.ollama_handler.generate_response(messages=messages_cot)
        assert isinstance(cot_response, ChatResponse) and isinstance(cot_response.response, str), "Response is not of type ChatResponse with string content."
        
        messages_subtasks = [
            {"role": "system", "content": system_extract_subtasks_prompt},
            {"role": "user", "content": cot_response.response}
        ]
        
        subtasks_response = self.ollama_handler.generate_response(
            messages=messages_subtasks,
            type=PlanSubtasks #type:ignore
        )
        
        assert isinstance(subtasks_response, ChatResponse) and isinstance(subtasks_response.response, PlanSubtasks), "Response is not of type PlanSubtasks."
        return subtasks_response.response
    
    def _plan_solutions(self, user_prompt:str) -> PlanSolutions:
        messages_cot = [
            {"role": "system", "content": system_generate_solutions_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        cot_response = self.ollama_handler.generate_response(messages=messages_cot)
        assert isinstance(cot_response, ChatResponse) and isinstance(cot_response.response, str), "Response is not of type ChatResponse with string content."
        
        messages_solutions = [
            {"role": "system", "content": system_extract_solutions_prompt},
            {"role": "user", "content": cot_response.response}
        ]
        
        solutions_response = self.ollama_handler.generate_response(
            messages=messages_solutions,
            type=PlanSolutions #type:ignore
        )
        
        assert isinstance(solutions_response, ChatResponse) and isinstance(solutions_response.response, PlanSolutions), "Response is not of type PlanSolutions."
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
    
    def plan(self, base_task:BaseTask, test_suite: TestSuite, is_final:bool=False, use_buffer:bool=False)-> PlanResponse:
        # Passo 1: Buscar tarefas similares no buffer já realizadas
        similar_tasks = self._find_similar_tasks(base_task, top_k=3) if use_buffer else "No similar tasks found."
        
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
                # Paasso 3.3 Caso tenha pelo menos 2 subtarefas, retornar o plano de subtarefas
                if len(subtasks.subtasks) >=2:
                    return PlanResponse(
                        reasoning=plan_response.reasoning,
                        result_type='subtasks',
                        subtasks=subtasks.subtasks
                    )
        
        # Passo 4: Caso seja o ramo máximo de decomposição, ou o resultado do plano seja soluções, o modelo deverá crar as soluções
        solutions = self._plan_solutions(user_prompt)
        return PlanResponse(
            reasoning=None,
            result_type='solutions',
            solutions=solutions.solutions
        )
    
    def save_history(self, task:Task)->str:
        task_dict = task.model_dump()
        del task_dict['test_suite']
        del task_dict['template']
        del task_dict['function_name']
        del task_dict['args']
        del task_dict['keywords']
        task_dict_str = json.dumps(task_dict, indent=2)
        
        messages = [
            {"role": "system", "content": create_template_prompt},
            {"role": "user", "content": task_dict_str}
        ]
        
        response = self.ollama_handler.generate_response(messages=messages)
        assert isinstance(response, ChatResponse) and isinstance(response.response, str), "Response is not of type ChatResponse with string content."
        
        task.template = response.response
        
        self.vector_buffer.create(task)
        return response.response