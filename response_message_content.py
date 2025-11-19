
def sum_two_numbers(a: int, b: int) -> int:
    return a + b

import sys

for line in sys.stdin:
    try:
        num1, num2 = line.strip().split(",")
        result = sum_two_numbers(int(num1), int(num2))
        print(result)
    except ValueError:
        print('ValueError')