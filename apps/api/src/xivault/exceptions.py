"""XiVault standard API exceptions and error models."""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class XiVaultAPIException(HTTPException):
    """Base API exception that adheres to the CodeVault/XiVault error contract."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
        details: Any = None,
    ):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.details = details


class UnauthorizedException(XiVaultAPIException):
    def __init__(self, message: str = "Invalid or missing authentication credentials."):
        super().__init__(
            status_code=401,
            code="unauthorized",
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidCredentialsException(XiVaultAPIException):
    def __init__(self, message: str = "Invalid username or password."):
        super().__init__(
            status_code=401,
            code="invalid_credentials",
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidRefreshTokenException(XiVaultAPIException):
    def __init__(self, message: str = "Invalid or expired refresh token."):
        super().__init__(status_code=401, code="invalid_refresh_token", message=message)


class RefreshTokenReuseException(XiVaultAPIException):
    def __init__(self, message: str = "Refresh token reuse detected. All sessions revoked."):
        super().__init__(status_code=401, code="refresh_token_reuse", message=message)


class ForbiddenException(XiVaultAPIException):
    def __init__(self, message: str = "Account state forbids access."):
        super().__init__(status_code=403, code="forbidden", message=message)


class NotFoundException(XiVaultAPIException):
    def __init__(self, code: str = "file_not_found", message: str = "Resource not found."):
        super().__init__(status_code=404, code=code, message=message)


class ConflictException(XiVaultAPIException):
    def __init__(self, code: str, message: str):
        super().__init__(status_code=409, code=code, message=message)


class FileTooLargeException(XiVaultAPIException):
    def __init__(self, message: str = "File size exceeds the 1 MiB limit."):
        super().__init__(status_code=413, code="file_too_large", message=message)


class ValidationException(XiVaultAPIException):
    def __init__(self, code: str = "validation_error", message: str = "Request validation failed."):
        super().__init__(status_code=422, code=code, message=message)


class RateLimitedException(XiVaultAPIException):
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            status_code=429,
            code="rate_limited",
            message=message,
            headers={"Retry-After": "60"},
        )


class QuotaExceededException(XiVaultAPIException):
    def __init__(self, message: str = "Storage quota exceeded (5 MiB limit)."):
        super().__init__(status_code=507, code="quota_exceeded", message=message)


async def xivault_exception_handler(request: Request, exc: XiVaultAPIException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    headers = {"X-Request-ID": request_id}
    if exc.headers:
        headers.update(exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
            }
        },
    )
