from typing import List
from modules.schema.task import Task

system_join_tasks_prompt = """
You are a skilled software developer tasked with integrating code from multiple subtasks into a single cohesive solution.

You will receive as user input the main task, and a series of subtasks (functions) that have been resolved individually, along with a framework for how these functions should be integrated into the main task.

You must return the complete unified code, ensuring that all functions from the subtasks are correctly incorporated into the main task according to the provided skeleton.
"""

main_task_template = """
MAIN TASK:

FUNCTION NAME: {function_name}
FUNCION_ARGS:
{function_args}
DEFINITION: {definition}
"""

subtask_temaplte = """
SUBTASK {idx}:
FUNCTION NAME: {function_name}
FUNCION_ARGS:
{function_args}
DEFINITION: {definition}
CODE:
{code}
"""

def join_tasks(main_task:Task, subtasks:List[Task], skeleton:str)->str:
    user_prompt = main_task_template.format(
        function_name=main_task.function_name,
        function_args="\n".join(arg.show(1) for arg in main_task.args),
        definition=main_task.definition
    )
    for idx, subtask in enumerate(subtasks, 1):
        user_prompt += subtask_temaplte.format(
            idx=idx,
            function_name=subtask.function_name,
            function_args="\n".join(arg.show(1) for arg in subtask.args),
            definition=subtask.definition,
            code=subtask.code
        )
    user_prompt += f"\nSKELETON:\n{skeleton}\n\nPlease provide the complete unified code integrating all subtasks into the main task."
    return user_prompt
    