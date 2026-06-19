import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError, app_error_handler


def create_error_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/validation-error")
    async def validation_error() -> None:
        raise AppError(
            code="STORY_FILE_REQUIRED",
            message="Choose a Markdown story file to continue.",
            http_status=422,
        )

    return app


@pytest.mark.asyncio
async def test_route_app_error_returns_standard_json() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_error_app()), base_url="http://test"
    ) as client:
        response = await client.get(
            "/validation-error", headers={"Accept": "application/json"}
        )

    assert response.status_code == 422
    assert response.json() == {
        "ok": False,
        "error": {
            "code": "STORY_FILE_REQUIRED",
            "message": "Choose a Markdown story file to continue.",
            "details": {},
        },
    }


@pytest.mark.asyncio
async def test_route_app_error_returns_htmx_partial() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_error_app()), base_url="http://test"
    ) as client:
        response = await client.get(
            "/validation-error",
            headers={"HX-Request": "true", "Accept": "text/html"},
        )

    assert response.status_code == 422
    assert "Choose a Markdown story file to continue." in response.text
    assert "STORY_FILE_REQUIRED" in response.text
    assert "Traceback" not in response.text
