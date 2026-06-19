from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.schemas.errors import ErrorDetail, ErrorResponse


templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}

    def to_response_model(self) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


async def app_error_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, AppError):
        raise exc

    response = exc.to_response_model()
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    wants_json = "application/json" in request.headers.get("accept", "")

    if wants_json and not is_htmx:
        return JSONResponse(
            status_code=exc.http_status,
            content=response.model_dump(mode="json"),
        )

    return templates.TemplateResponse(
        request=request,
        name="partials/_flash.html",
        context={
            "flash_message": exc.message,
            "flash_kind": "error",
            "error_code": exc.code,
        },
        status_code=exc.http_status,
    )
