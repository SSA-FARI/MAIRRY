import logging
import traceback
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.schema import ApiModel

logger = logging.getLogger(__name__)


class ErrorBody(ApiModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    error: ErrorBody


@dataclass
class AppError(Exception):
    code: ErrorCode
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    details: dict[str, Any] = dataclass_field(default_factory=dict)


def _response(status_code: int, error: ErrorBody) -> JSONResponse:
    payload = ErrorResponse(error=error).model_dump(mode="json", by_alias=True)
    return JSONResponse(status_code=status_code, content=payload)


def _sanitized_traceback(exc: Exception) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "unavailable"
    return " -> ".join(f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _response(
        exc.status_code,
        ErrorBody(code=exc.code, message=exc.message, details=exc.details),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    field_errors = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    is_contract_confirmation = (
        request.method == "PUT"
        and request.url.path.startswith("/api/documents/")
        and request.url.path.endswith("/confirm")
        and all(error["loc"] and error["loc"][0] == "body" for error in exc.errors())
    )
    response_status = (
        status.HTTP_422_UNPROCESSABLE_CONTENT
        if is_contract_confirmation
        else status.HTTP_400_BAD_REQUEST
    )
    error_code = (
        ErrorCode.EXTRACTION_VALIDATION_ERROR
        if is_contract_confirmation
        else ErrorCode.VALIDATION_ERROR
    )
    return _response(
        response_status,
        ErrorBody(
            code=error_code,
            message="요청 값을 확인해 주세요.",
            details={"fields": field_errors},
        ),
    )


async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    is_not_found = exc.status_code == status.HTTP_404_NOT_FOUND
    code = ErrorCode.RESOURCE_NOT_FOUND if is_not_found else ErrorCode.VALIDATION_ERROR
    message = "요청한 리소스를 찾을 수 없습니다." if is_not_found else "요청을 처리할 수 없습니다."
    return _response(exc.status_code, ErrorBody(code=code, message=message, details={}))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = str(uuid4())
    logger.error(
        "Unhandled API error: method=%s path=%s errorType=%s traceId=%s traceback=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
        trace_id,
        _sanitized_traceback(exc),
    )
    return _response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorBody(
            code=ErrorCode.INTERNAL_ERROR,
            message="일시적인 오류가 발생했습니다.",
            details={"traceId": trace_id},
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
