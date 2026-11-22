from fastapi import HTTPException, status


class BaseAppException(HTTPException):

    def __init__(self, status_code: int, code: str, message: str, headers: dict | None = None) -> None:
        """Initializes a structured application HTTP exception.

        Args:
            status_code (int): HTTP status code for the response.
            code (str): Application-specific error code string.
            message (str): Detailed error description.
            headers (dict | None, optional): Optional dictionary of HTTP headers. Defaults to None.
        """
        self.code = code
        self.message = message
        super().__init__(status_code=status_code, detail=message, headers=headers)


class NotFoundException(BaseAppException):

    def __init__(self, detail: str = "Resource not found") -> None:
        """Initializes an HTTP 404 Not Found application exception.

        Args:
            detail (str, optional): Custom error message detailing the missing resource.
        """
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=detail
        )


class BadRequestException(BaseAppException):

    def __init__(self, detail: str = "Bad request") -> None:
        """Initializes an HTTP 400 Bad Request application exception.

        Args:
            detail (str, optional): Custom error message detailing the invalid request.
        """
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            message=detail
        )


class ConflictException(BaseAppException):

    def __init__(self, detail: str = "Resource conflict") -> None:
        """Initializes an HTTP 409 Conflict application exception.

        Args:
            detail (str, optional): Custom error message detailing the conflicting resource.
        """
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message=detail
        )


class UnauthorizedException(BaseAppException):

    def __init__(self, detail: str = "Unauthorized") -> None:
        """Initializes an HTTP 401 Unauthorized application exception.

        Args:
            detail (str, optional): Custom error message detailing the authentication failure.
        """
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(BaseAppException):

    def __init__(self, detail: str = "Access forbidden") -> None:
        """Initializes an HTTP 403 Forbidden application exception.

        Args:
            detail (str, optional): Custom error message detailing the forbidden access.
        """
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=detail
        )


class TooManyRequestsException(BaseAppException):

    def __init__(self, detail: str = "Too many requests", retry_after: int = 60) -> None:
        """Initializes an HTTP 429 Too Many Requests application exception.

        Args:
            detail (str, optional): Custom error message detailing the rate limit.
            retry_after (int, optional): Seconds the client should wait before retrying.
        """
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="TOO_MANY_REQUESTS",
            message=detail,
            headers={"Retry-After": str(retry_after)},
        )


class ServiceUnavailableException(BaseAppException):

    def __init__(self, detail: str = "Service unavailable") -> None:
        """Initializes an HTTP 503 Service Unavailable application exception.

        Args:
            detail (str, optional): Custom error message detailing the external service failure.
        """
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
            message=detail
        )
