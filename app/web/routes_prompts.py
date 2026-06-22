from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.openai_prompt_service import OpenAIPromptService
from app.services.project_service import ProjectService
from app.services.prompt_service import PromptService
from app.services.scene_service import SceneService


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _project_service(settings: Settings) -> ProjectService:
    return ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
        enable_ip_adapter_faceid=settings.enable_ip_adapter_faceid,
        force_low_vram_mode=settings.force_low_vram_mode,
    )


def _context(
    settings: Settings, project_id: str, **values: object
) -> dict[str, object]:
    prompt_list = PromptService(settings.projects_root).get_prompts(project_id)
    scene_list = SceneService(settings.projects_root).get_scenes(project_id)
    active_scenes = scene_list.active_scenes if scene_list is not None else []
    return {
        "page_title": "Prompt Review",
        "project": _project_service(settings).get_project(project_id),
        "prompt_list": prompt_list,
        "prompts": prompt_list.prompts if prompt_list else [],
        "scenes_approved": bool(active_scenes)
        and all(scene.status.value == "approved" for scene in active_scenes),
        **values,
    }


@router.get("/projects/{project_id}/prompts", response_class=HTMLResponse)
async def prompts_page(request: Request, project_id: str) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="prompt_review.html",
        context=_context(settings, project_id),
    )


@router.post("/projects/{project_id}/prompts/generate", response_class=HTMLResponse)
async def generate_prompts(request: Request, project_id: str) -> Response:
    settings = get_settings()
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    try:
        prompt_list = OpenAIPromptService(
            settings.projects_root, mock_mode=True
        ).generate_prompts(project_id)
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/_prompt_list.html" if is_htmx else "prompt_review.html",
            context=_context(
                settings,
                project_id,
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )

    if is_htmx:
        return templates.TemplateResponse(
            request=request,
            name="partials/_prompt_list.html",
            context={
                **_context(settings, project_id),
                "prompt_list": prompt_list,
                "prompts": prompt_list.prompts,
                "flash_message": "Image prompts are ready for review.",
                "flash_kind": "success",
            },
        )
    return RedirectResponse(url=f"/projects/{project_id}/prompts", status_code=303)
