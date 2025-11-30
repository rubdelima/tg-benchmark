from dataclasses import dataclass
import ast
from typing import List, Optional
from pathlib import Path
from mypy import api
import re
from tempfile import NamedTemporaryFile

CODE_BLOCK_PATTERN = re.compile(r"```(?:python|py)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
ERROR_RE = re.compile(r'^(?P<file>.+?):(?P<line>\d+): error: (?P<msg>.+?)(?: \[(?P<code>[^\]]+)\])?$')
WARNING_RE = re.compile(r'^(?P<file>.+?):(?P<line>\d+): warning: (?P<msg>.+?)(?: \[(?P<code>[^\]]+)\])?$')
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
    
@dataclass
class CheckResult:
    success: bool
    code : str
    errors: List[str]
    warnings: Optional[List[str]] = None


class GeneratorCodeBaseModel:
    @staticmethod
    def _is_valid_python_code(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except:
            return False
    
    @staticmethod
    def clean_code(code: str) -> Optional[str]:
        code_blocks =  CODE_BLOCK_PATTERN.findall(code)
        if len(code_blocks) == 1:
            return code_blocks[0].strip()
        elif len(code_blocks) > 1:
            return None
        return code.strip()
        
    @staticmethod
    def _mypy_check(code: str,ignore_warnings: bool,ignore_function: Optional[str] = None) -> CheckResult:
        
        with NamedTemporaryFile(mode='w+', suffix='.py', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(code)
            temp_file_path = Path(temp_file.name)
        stdout, stderr, exit_status = api.run([str(temp_file_path)])
        temp_file_path.unlink()
        
        clean_output = ANSI_RE.sub('', stdout)

        errors: List[str] = []
        warnings: List[str] = []

        for line in clean_output.splitlines():
            line = line.strip()

            if not line:
                continue

            if (m_err := ERROR_RE.match(line)):
                msg = m_err.group("msg")
                if ignore_function and f'"{ignore_function}"' in msg:
                    continue
                errors.append(line)

            elif WARNING_RE.match(line):
                if not ignore_warnings:
                    warnings.append(line)

        success = (exit_status == 0) or (len(errors) == 0)

        return CheckResult(
            success=success,
            code=code,
            errors=errors,
            warnings=None if ignore_warnings else warnings
        )
    

    def parse_code(self, response: str, ignore_warnings: bool=False, ignore_function: Optional[str] = None) -> CheckResult:
        parsed_code = self._is_valid_python_code(response)
        
        if parsed_code is True:
            return self._mypy_check(response, ignore_warnings=ignore_warnings, ignore_function=ignore_function)
        
        code_blocks =  CODE_BLOCK_PATTERN.findall(response)
        
        if not code_blocks:
            return CheckResult(
                success=False,
                code="",
                errors=["The response does not contain valid code. Please ensure the response includes valid Python code."],
            )
            
        elif len(code_blocks) > 1:
            return CheckResult(
                success=False,
                code="",
                errors=["Multiple code blocks found in the response. Please provide a response with a single code block or a raw python code."],
            )
        
        return self._mypy_check(code_blocks[0], ignore_warnings=ignore_warnings, ignore_function=ignore_function)