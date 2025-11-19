import ast
from typing import Union, Literal
import re

CODE_BLOCK_PATTERN = re.compile(r"```(?:python)?\s*(.*?)\s*```", re.DOTALL)

def _is_valid_python_code(code: str) -> Union[Literal[True], SyntaxError]:
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        return e
@staticmethod
def _extract_code_blocks(response: str) -> list[str]:
    return CODE_BLOCK_PATTERN.findall(response)

def parse_code(response: str) -> str:
    parsed_code = _is_valid_python_code(response)
    if parsed_code is True:
        return response
    code_blocks =  _extract_code_blocks(response)
    if not code_blocks:
        raise ValueError(
            "The response does not contain valid code. Please ensure the response includes valid Python code.")
    elif len(code_blocks) > 1:
        raise ValueError(
            "Multiple code blocks found in the response. Please provide a response with a single code block or a raw python code.")
    code_block_parsed = _is_valid_python_code(code_blocks[0])
    if code_block_parsed is True:
        return code_blocks[0]
    value_error_msg = (
        "This response does not contain a valid Python code. Please ensure the response includes valid Python code.\n"
        f"SyntaxError in Raw Response: {parsed_code}\n"
        f"SyntaxError in Raw Block (msg) : {code_block_parsed.msg}\n"
        f"SyntaxError in Raw Block (lineno) : {code_block_parsed.lineno}\n"
        f"SyntaxError in Raw Block (offset) : {code_block_parsed.offset}\n"
        f"SyntaxError in Raw Block (text) : {code_block_parsed.text}\n"
        f"SyntaxError in Code Block: {code_block_parsed}"
        f"SyntaxError in Code Block (msg) : {code_block_parsed.msg}\n"
        f"SyntaxError in Code Block (lineno) : {code_block_parsed.lineno}\n"
        f"SyntaxError in Code Block (offset) : {code_block_parsed.offset}\n"
        f"SyntaxError in Code Block (text) : {code_block_parsed.text}\n"
    )
    raise ValueError(value_error_msg)