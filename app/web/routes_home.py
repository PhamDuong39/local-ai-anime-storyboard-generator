from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/health")
async def healthcheck() -> dict[str, str | bool]:
    return {
        "ok": True,
        "status": "healthy",
        "app": "local-ai-anime-storyboard-generator",
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"page_title": "Local AI Anime Storyboard Generator"},
    )
