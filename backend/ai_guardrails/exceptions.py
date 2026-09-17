class GuardrailViolation(ValueError):
    def __init__(self, message, code='guardrail_blocked'):
        super().__init__(message)
        self.code = code