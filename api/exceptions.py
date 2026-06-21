"""Erros produzidos pela camada HTTP da aplicacao."""


class ApiError(Exception):
    error_code = "API_ERROR"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RateLimitExceededError(ApiError):
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "Limite de consultas excedido. Tente novamente em alguns segundos."
        )
        self.retry_after_seconds = retry_after_seconds
