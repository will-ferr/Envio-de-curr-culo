"""Erros de aplicação com código estável. A camada HTTP traduz para status."""


class AppError(Exception):
    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code:
            self.code = code


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status = 409
    code = "CONFLICT"


class BusinessRule(AppError):
    status = 422
    code = "BUSINESS_RULE"


class Unauthorized(AppError):
    status = 401
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN"


class TooManyRequests(AppError):
    status = 429
    code = "TOO_MANY_REQUESTS"


class ExternalError(AppError):
    """Serviço externo (site da vaga, SMTP, Telegram) falhou."""

    status = 502
    code = "EXTERNAL_ERROR"
