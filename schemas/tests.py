from typing import List
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    test_input: str = Field(..., description="Input that caused the test to fail")
    expected_output: str = Field(..., description="Expected output of the test")
    actual_output: str = Field(..., description="Actual output of the test")
    error_message: str = Field(..., description="Error message associated with the test")
  
class TestsResult(BaseModel):
    raw_code : str = Field(..., description="Raw code that was executed for the tests")
    total_time: float = Field(..., description="Total time taken to run all tests in seconds")
    passed_tests: int = Field(..., description="Number of tests that passed successfully")
    total_tests: int = Field(..., description="Total number of tests executed")
    success_rate: float = Field(..., description="Percentage of tests that passed successfully (0.0 - 1.0 1.0 means 100%)")
    errors: list[ErrorDetail] = Field(..., description="List of non-passing tests during execution")
    
    def display_errors(self) -> str:
        if not self.errors:
            return "All tests passed successfully."
        
        error_report = "Test Failures:\n"
        for i, error in enumerate(self.errors):
            error_report += (
                f"<input>\n{error.test_input}</input>\n"
                f"<expected_output>\n{error.expected_output}</expected_output>\n"
                f"<actual_output>\n{error.actual_output}</actual_output>\n"
                f"<error_message>\n{error.error_message}</error_message>\n\n"
            )
        return error_report.strip()

class TestCase(BaseModel):
    inputs : str = Field(..., description="Input for the test case")
    expected_output: str = Field(..., description="Expected output for the test case")

class TestSuiteBase(BaseModel):
    test_cases: List[TestCase] = Field(..., description="List of test cases in the suite")

class TestSuite(TestSuiteBase):
    test_code_raw:str = Field(..., description="Raw code for the test suite")
    
    def test_cases_summary(self, no_code=False) -> str:
        summary = ""
        if not no_code:
            summary = "Code for tests:\n"
            summary += self.test_code_raw + "\n\n"
        summary += "Test Cases Summary:\n"
        for i, tc in enumerate(self.test_cases):
            summary += f"Test Case {i+1}:\n<input>\n{tc.inputs}</input>\n<expected_output>\n{tc.expected_output}</expected_output>\n\n"
        return summary.strip()

class TestSuiteComplete(TestSuite):
    function_name: str = Field(..., description="Name of the function being tested")

__all__ = ["TestCase", "TestSuite", "TestsResult", "ErrorDetail", "TestSuiteComplete"]