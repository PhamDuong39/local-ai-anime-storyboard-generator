from pathlib import Path
from typing import cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.prompt import Prompt
from app.schemas.scene import Scene
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
    scenes_approved = bool(active_scenes) and all(
        scene.status.value == "approved" for scene in active_scenes
    )
    approved_scenes = active_scenes if scenes_approved else []
    prompts = prompt_list.prompts if prompt_list else []
    prompts_ready = (
        bool(prompt_list)
        and bool(prompts)
        and len(prompts) == len(approved_scenes)
        and all(prompt.status.value == "ready" for prompt in prompts)
    )
    return {
        "page_title": "Prompt Review",
        "project": _project_service(settings).get_project(project_id),
        "prompt_list": prompt_list,
        "prompts": prompts,
        "approved_scenes": approved_scenes,
        "prompt_by_scene_id": {prompt.scene_id: prompt for prompt in prompts},
        "scenes_approved": scenes_approved,
        "prompts_ready": prompts_ready,
        **values,
    }


def _prompt_context(
    settings: Settings,
    project_id: str,
    scene_id: str,
    **values: object,
) -> dict[str, object]:
    context = _context(settings, project_id)
    prompt_by_scene_id = cast(dict[str, Prompt], context["prompt_by_scene_id"])
    approved_scenes = cast(list[Scene], context["approved_scenes"])
    prompt = prompt_by_scene_id.get(scene_id)
    scene = next((item for item in approved_scenes if item.scene_id == scene_id), None)
    return {
        **context,
        "card_scene_id": scene_id,
        "scene": scene,
        "prompt": prompt,
        **values,
    }


def _fallback_prompt_card(
    request: Request,
    settings: Settings,
    project_id: str,
    scene_id: str,
    exc: AppError,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/_prompt_card.html",
        context=_prompt_context(
            settings,
            project_id,
            scene_id,
            flash_message=exc.message,
            flash_kind="error",
            error_code=exc.code,
        ),
        status_code=exc.http_status,
    )


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
            settings.projects_root,
            mock_mode=settings.openai_mock_mode,
            model=settings.openai_prompt_model,
            api_key=settings.openai_api_key,
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


@router.post("/projects/{project_id}/prompts/{scene_id}", response_class=HTMLResponse)
async def update_prompt(
    request: Request,
    project_id: str,
    scene_id: str,
    positive_prompt: str = Form(""),
    negative_prompt: str = Form(""),
) -> Response:
    settings = get_settings()
    try:
        prompt = PromptService(settings.projects_root).update_prompt(
            project_id,
            scene_id,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
    except AppError as exc:
        return _fallback_prompt_card(request, settings, project_id, scene_id, exc)

    scene_list = SceneService(settings.projects_root).get_scenes(project_id)
    scene = (
        next(
            (item for item in scene_list.active_scenes if item.scene_id == scene_id),
            None,
        )
        if scene_list
        else None
    )
    return templates.TemplateResponse(
        request=request,
        name="partials/_prompt_card.html",
        context={
            **_context(settings, project_id),
            "card_scene_id": scene_id,
            "scene": scene,
            "prompt": prompt,
            "flash_message": "Prompt saved.",
            "flash_kind": "success",
        },
    )
