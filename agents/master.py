
from agents.developer import Ellian
from agents.judge import Will
from agents.reseacher import Thifany

from schemas.tests import TestSuiteBase
from modules.llm import OllamaHandler
from modules.dataloader import QuestionDataset
from modules.test_runner import TestRunner
from agents.reseacher.prompt_question import test_cases_template, create_question_solution_user

class Davi:
    def __init__(self, handler: OllamaHandler, max_retries: int = 2):
        self.llm = handler
        self.max_retries = max_retries
        self.dev = Ellian(self.llm, verbosity=2, generation_retry_attempts=max_retries)
        self.judge = Will(self.llm)
        self.test_runner = TestRunner()
        self.researcher = Thifany(self.llm)
    
    def create_question_template(self, question_dataset: QuestionDataset) -> str:
        test_cases_str = "\n".join(
            test_cases_template.format(index=i+1, input=tc.inputs, output=tc.expected_output)
            for i, tc in enumerate(question_dataset.public_test_cases)
        )
        
        return create_question_solution_user.format(
            title=question_dataset.title,
            content=question_dataset.content,
            tests_cases=test_cases_str
        )
    
    def solve_question_dataset(self, question_dataset: QuestionDataset)->tuple[str, list[dict]]:
        best_code = ""
        best_solution = ""
        best_score = -1.0
        test_suite = TestSuiteBase(test_cases=question_dataset.private_test_cases)
        outputs = []
        try:
            question_template = self.create_question_template(question_dataset)
            outputs.append({"question_template": question_template})
            # Passo 1: Pesquisador Busca Informações e Gera Primieira Solução
            solution = self.researcher.create_question_solution(question_template)
            # Loop de Melhoria Contínua
            attempts = 0
            outputs.append({f"solution_{attempts}": solution})

            while True:
                # Passo 2: Desenvolvedor Gera Código com Base na Solução Pensada
                code = self.dev.generate_code_from_master(question_template, solution)
                outputs.append({f"code_{attempts}": code})

                # Passo 3: Executor de Testes Roda a Suíte de Testes
                test_result = self.test_runner.run(test_suite, code)
                
                for test_error in test_result.errors[:5]:  # Limita a 5 erros para evitar excesso de informação
                    outputs.append({f"test_failure_{attempts}": {
                        "test_input": test_error.test_input,
                        "expected_output": test_error.expected_output,
                        "actual_output": test_error.actual_output,
                        "error_message": test_error.error_message
                    }})

                # Atualiza Melhor Código e Solução se Necessário
                if test_result.success_rate >= best_score:
                    best_code = code
                    best_solution = solution
                    best_score = test_result.success_rate

                # Encerra o loop se todos os testes passaram
                if test_result.success_rate == 1.0:
                    break
                
                attempts += 1
                if attempts >= self.max_retries:
                    break
                
                # Passo 4: Juiz Avalia o Código e Fornece nova Solução
                solution = self.judge.evaluate_and_suggest(question_template, code, solution, test_result, best_code, best_solution)
                outputs.append({f"solution_{attempts}": solution})
        finally:
            return best_code, outputs
        