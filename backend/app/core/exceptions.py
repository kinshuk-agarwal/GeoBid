"""Domain exceptions.

Services raise these; ``app.main`` maps them to HTTP responses so route
handlers stay thin and services stay HTTP-agnostic.
"""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class AuthenticationError(DomainError):
    status_code = 401


class PermissionDeniedError(DomainError):
    status_code = 403


class BusinessRuleError(DomainError):
    """A request was well-formed but violates a business rule (e.g. a low bid)."""

    status_code = 422
