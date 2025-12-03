import os
import sys
import time
import tempfile
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, List
from modules.logger import StatusContext, get_logger 

logger = get_logger(__name__)

# Ajuste os imports conforme a estrutura exata do seu projeto
from schemas.tests import TestSuiteBase, TestsResult, ErrorDetail, TestCase

class TestRunner:
    """
    Executor robusto de suítes de teste em PARALELO com timeout garantido.
    """
    
    def __init__(self, max_workers: int = 16, timeout: int = 5):
        self.max_workers = max_workers
        self.timeout = timeout

    def run(self, test_suite: TestSuiteBase, full_code: str) -> TestsResult:
        """
        Executa a suíte de testes contra o código fornecido.
        """
        total_tests = len(test_suite.test_cases)
        
        if total_tests == 0:
            return TestsResult(
                raw_code=full_code,
                total_time=0.0,
                passed_tests=0,
                total_tests=0,
                success_rate=0.0,
                errors=[]
            )

        passed_tests = 0
        errors: List[ErrorDetail] = []
        total_time = 0.0

        # Arquivo temporário com o código
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
            tmp_file_path = tmp_file.name
            tmp_file.write(full_code)

        try:
            with StatusContext(f"Run tests (0/{total_tests})...") as status:
                with ThreadPoolExecutor(max_workers=min(self.max_workers, total_tests)) as executor:
                    future_to_case = {
                        executor.submit(self._execute_single_case, tmp_file_path, case): case 
                        for case in test_suite.test_cases
                    }

                    completed = 0
                    for future in as_completed(future_to_case):
                        success, error_detail, exec_time = future.result()
                        total_time += exec_time
                        completed += 1

                        if success:
                            passed_tests += 1
                        elif error_detail:
                            errors.append(error_detail)

                        status.update(
                            f"Run tests ({completed}/{total_tests}) "
                            f"| ✅ {passed_tests} | ❌ {len(errors)}"
                        )

        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        success_rate = passed_tests / total_tests if total_tests > 0 else 0.0
        
        return TestsResult(
            raw_code=full_code,
            total_time=round(total_time, 4),
            passed_tests=passed_tests,
            total_tests=total_tests,
            success_rate=round(success_rate, 2),
            errors=errors
        )

    def _execute_single_case(self, script_path: str, test_case: TestCase) -> Tuple[bool, Optional[ErrorDetail], float]:
        """
        Roda um único caso de teste com timeout garantido via Timer.
        """
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        start_time = time.time()
        input_data = test_case.inputs 
        expected_data = test_case.expected_output
        timeout = self.timeout
        timed_out = False

        try:
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            
            # Timer que mata o processo se demorar demais
            def kill_proc():
                nonlocal timed_out
                timed_out = True
                try:
                    proc.kill()
                except:
                    pass
            
            timer = threading.Timer(timeout, kill_proc)
            timer.start()
            
            try:
                stdout_bytes, stderr_bytes = proc.communicate(input=input_data.encode('utf-8'))
                stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ""
                stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ""
                returncode = proc.returncode
            finally:
                timer.cancel()
            
            exec_time = time.time() - start_time
            
            if timed_out:
                return False, ErrorDetail(
                    test_input=input_data,
                    expected_output=expected_data,
                    actual_output="",
                    error_message=f"Timeout exceeded ({timeout}s)"
                ), exec_time
            
        except Exception as ex:
            exec_time = time.time() - start_time
            return False, ErrorDetail(
                test_input=input_data,
                expected_output=expected_data,
                actual_output="",
                error_message=f"Execution error: {str(ex)}"
            ), exec_time
        
        # Normalização
        actual_output = stdout.strip().replace('\r\n', '\n')
        expected_output_norm = expected_data.strip().replace('\r\n', '\n')
        
        if returncode != 0:
            return False, ErrorDetail(
                test_input=input_data,
                expected_output=expected_output_norm,
                actual_output=actual_output,
                error_message=f"Runtime Error (Exit Code {returncode}): {stderr.strip()}"
            ), exec_time

        if actual_output == expected_output_norm:
            return True, None, exec_time
        else:
            return False, ErrorDetail(
                test_input=input_data,
                expected_output=expected_output_norm,
                actual_output=actual_output,
                error_message="Output mismatch"
            ), exec_time