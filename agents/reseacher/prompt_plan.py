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
