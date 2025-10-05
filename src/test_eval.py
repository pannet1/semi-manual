class MyClass:
    def __init__(self, ltp, low):
        self._ltp = ltp
        self._low = low

    def evaluate_condition(self, condition: str) -> bool:
        # Controlled use of eval
        return eval(condition)


# Example usage
my_obj = MyClass(ltp=100, low=95)
condition = "self._ltp > self._low"  # Defined internally
print(my_obj.evaluate_condition(condition))  # Output: True
