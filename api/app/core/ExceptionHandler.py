from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.common.exceptions.AppExceptions import BaseAppException


class ExceptionHandler:

    @staticmethod
    def registerHandlers(app: FastAPI) -> None:
        """Registers global exception handlers to enforce the standard JSON error contract.

        Args:
            app (FastAPI): FastAPI application instance.
        """
        app.add_exception_handler(BaseAppException, ExceptionHandler.handleBaseAppException)
        app.add_exception_handler(RequestValidationError, ExceptionHandler.handleValidationException)
        app.add_exception_handler(Exception, ExceptionHandler.handleUnhandledException)

    @staticmethod
    async def handleBaseAppException(request: Request, exc: BaseAppException) -> JSONResponse:
        """Formats domain BaseAppException errors into {code, message} JSON responses.

        Args:
            request (Request): Incoming HTTP request.
            exc (BaseAppException): Raised application exception.

        Returns:
            JSONResponse: Standardized JSON error payload.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
            headers=exc.headers
        )

    @staticmethod
    async def handleValidationException(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Formats Pydantic request validation errors into the standard error schema.

        Args:
            request (Request): Incoming HTTP request.
            exc (RequestValidationError): FastAPI validation error.

        Returns:
            JSONResponse: Standardized HTTP 422 JSON error payload.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"code": "VALIDATION_ERROR", "message": str(exc.errors())}
        )

    @staticmethod
    async def handleUnhandledException(request: Request, exc: Exception) -> JSONResponse:
        """Catches unexpected server exceptions without leaking internal stack traces.

        Args:
            request (Request): Incoming HTTP request.
            exc (Exception): Unhandled runtime exception.

        Returns:
            JSONResponse: Standardized HTTP 500 JSON error payload.
        """
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected server error occurred."}
        )
