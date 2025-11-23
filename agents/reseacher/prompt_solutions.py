from agents.reseacher.prompt_plan import user_task_input

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