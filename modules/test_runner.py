import os
import sys
import time
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, List
from modules.logger import StatusContext, get_logger 

logger = get_logger(__name__)

# Ajuste os imports conforme a estrutura exata do seu projeto
from schemas.tests import TestSuiteBase, TestsResult, ErrorDetail, TestCase

class TestRunner:
    """
    Executor robusto de suítes de teste em paralelo.
    Adaptado para os Schemas Pydantic fornecidos (TestCase.inputs vs ErrorDetail.test_input).
    """
    
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def run(self, test_suite: TestSuiteBase, full_code: str) -> TestsResult:
        """
        Executa a suíte de testes contra o código fornecido (já com a função implementada).
        """
        total_tests = len(test_suite.test_cases)
        
        # Caso base: sem testes
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

        # Criação do arquivo temporário com o código completo
        # Delete=False é necessário para que subprocessos possam abrir o arquivo pelo path
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
            tmp_file_path = tmp_file.name
            tmp_file.write(full_code)

        try:

            total_tests = len(test_suite.test_cases)
            completed_tests = 0

            # 1. Inicia o Contexto de Status
            with StatusContext(f"Run tests (0/{total_tests})...") as status:

                with ThreadPoolExecutor(max_workers=min(self.max_workers, total_tests)) as executor:
                    future_to_case = {
                        executor.submit(self._execute_single_case, tmp_file_path, case): case 
                        for case in test_suite.test_cases
                    }

                    for future in as_completed(future_to_case):
                        success, error_detail, exec_time = future.result()
                        total_time += exec_time

                        # Atualiza contadores de lógica
                        completed_tests += 1
                        if success:
                            passed_tests += 1
                        else:
                            if error_detail:
                                errors.append(error_detail)

                        # 2. ATUALIZA A UI AQUI
                        # Mostra o progresso e quantos passaram/falharam em tempo real
                        failed_tests = len(errors)
                        status.update(
                            f"Run tests ({completed_tests}/{total_tests}) "
                            f"| ✅ {passed_tests} | ❌ {failed_tests}"
                        )

        finally:
            # Garante a remoção do arquivo temporário mesmo se houver crash
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        # Montagem do Resultado Final
        # Evita divisão por zero
        success_rate = passed_tests / total_tests if total_tests > 0 else 0.0
        
        return TestsResult(
            raw_code=full_code,
            total_time=round(total_time, 4),
            passed_tests=passed_tests,
            total_tests=total_tests,
            success_rate=round(success_rate, 2),
            errors=errors
        )

    def _execute_single_case(self, script_path: str, test_case: TestCase, timeout: int = 5) -> Tuple[bool, Optional[ErrorDetail], float]:
        """
        Roda um único caso de teste em um processo isolado.
        Retorna: (Sucesso, Detalhe do Erro, Tempo de Execução)
        """
        # Copia o environment atual e força UTF-8 para evitar erros de encoding
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        start_time = time.time()
        
        # CORREÇÃO DE ESQUEMA: TestCase usa 'inputs' (plural)
        input_data = test_case.inputs 
        expected_data = test_case.expected_output

        try:
            # sys.executable garante que estamos usando o mesmo Python do venv atual
            result = subprocess.run(
                [sys.executable, script_path],
                input=input_data,  # Passando o input correto
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                check=False # Não lança exceção automaticamente, checamos o returncode
            )
            
            exec_time = time.time() - start_time
            
            # --- NORMALIZAÇÃO & COMPARAÇÃO ---
            
            # Normaliza quebras de linha (Windows \r\n -> Unix \n) e remove espaços das pontas
            actual_output = result.stdout.strip().replace('\r\n', '\n')
            expected_output_norm = expected_data.strip().replace('\r\n', '\n')
            
            logger.debug(f"Return code: {result.returncode}")
            logger.debug(f"Normalized actual output:\n{actual_output}")
            logger.debug(f"Normalized expected output:\n{expected_output_norm}")
            logger.debug(f"Response OK: {actual_output == expected_output_norm}")
            
            # 1. Verifica Erros de Runtime (Crash, EOFError, SyntaxError que passou batido)
            if result.returncode != 0:
                # O código falhou (Exit Code 1 ou outro). O erro está no stderr.
                return False, ErrorDetail(
                    test_input=input_data,  # Popula ErrorDetail.test_input com TestCase.inputs
                    expected_output=expected_output_norm,
                    actual_output=actual_output, # O que printou antes de morrer
                    error_message=f"Runtime Error (Exit Code {result.returncode}): {result.stderr.strip()}"
                ), exec_time

            # 2. Verifica Lógica de Negócio (Output Match)
            if actual_output == expected_output_norm:
                return True, None, exec_time
            else:
                return False, ErrorDetail(
                    test_input=input_data,
                    expected_output=expected_output_norm,
                    actual_output=actual_output,
                    error_message="Output mismatch"
                ), exec_time

        except subprocess.TimeoutExpired:
            return False, ErrorDetail(
                test_input=input_data,
                expected_output=expected_data, # Usa o raw aqui pois não processamos
                actual_output="",
                error_message=f"Timeout exceeded ({timeout}s)"
            ), timeout

        except Exception as e:
            return False, ErrorDetail(
                test_input=input_data,
                expected_output=expected_data,
                actual_output="",
                error_message=f"Infrastructure Execution Error: {str(e)}"
            ), 0.0