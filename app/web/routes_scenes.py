from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.scene import SceneList
from app.services.character_service import CharacterService
from app.services.openai_scene_service import OpenAISceneService
from app.services.project_service import ProjectService
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


def _scene_service(settings: Settings) -> SceneService:
    return SceneService(settings.projects_root)


def _context(
    *, project: object, scene_list: SceneList | None, **values: object
) -> dict[str, object]:
    active_count = len(scene_list.active_scenes) if scene_list else 0
    return {
        "page_title": "Scene Review",
        "project": project,
        "scene_list": scene_list,
        "scenes": scene_list.scenes if scene_list else [],
        "active_count": active_count,
        **values,
    }


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _names(value: str) -> list[str]:
    return [name.strip() for name in value.split(",") if name.strip()]


async def _ordered_ids(request: Request) -> list[str]:
    if "application/json" in request.headers.get("content-type", ""):
        try:
            body = await request.json()
        except ValueError:
            return []
        scene_ids = body.get("scene_ids", []) if isinstance(body, dict) else []
        return [value for value in scene_ids if isinstance(value, str)]
    form = await request.form()
    return [str(value) for value in form.getlist("scene_ids")]


@router.get("/projects/{project_id}/scenes", response_class=HTMLResponse)
async def scenes_page(request: Request, project_id: str) -> HTMLResponse:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    scene_list = _scene_service(settings).get_scenes(project_id)
    characters = CharacterService(settings.projects_root).get_characters(project_id)
    known_names = {item.name for item in characters.characters} if characters else set()
    detected_names = (
        {name for scene in scene_list.scenes for name in scene.characters}
        if scene_list
        else set()
    )
    return templates.TemplateResponse(
        request=request,
        name="scene_review.html",
        context=_context(
            project=project,
            scene_list=scene_list,
            missing_character_names=sorted(detected_names - known_names),
        ),
    )


@router.post("/projects/{project_id}/scenes/split", response_class=HTMLResponse)
async def split_scenes(request: Request, project_id: str) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    try:
        scene_list = OpenAISceneService(
            settings.projects_root, mock_mode=True
        ).split_story_into_scenes(project_id)
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_list.html" if is_htmx else "scene_review.html",
            context=_context(
                project=project,
                scene_list=_scene_service(settings).get_scenes(project_id),
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )
    if is_htmx:
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_list.html",
            context=_context(
                project=project,
                scene_list=scene_list,
                flash_message="Draft scenes are ready for review.",
                flash_kind="success",
            ),
        )
    return RedirectResponse(url=f"/projects/{project_id}/scenes", status_code=303)


@router.post("/projects/{project_id}/scenes/reorder", response_class=HTMLResponse)
async def reorder_scenes(request: Request, project_id: str) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    try:
        scene_list = _scene_service(settings).reorder_scenes(
            project_id, await _ordered_ids(request)
        )
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_list.html",
            context=_context(
                project=project,
                scene_list=_scene_service(settings).get_scenes(project_id),
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )
    return templates.TemplateResponse(
        request=request,
        name="partials/_scene_list.html",
        context=_context(project=project, scene_list=scene_list),
    )


@router.post("/projects/{project_id}/scenes/approve", response_class=HTMLResponse)
async def approve_scenes(request: Request, project_id: str) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    try:
        _scene_service(settings).approve_scenes(project_id)
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_list.html",
            context=_context(
                project=project,
                scene_list=_scene_service(settings).get_scenes(project_id),
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )
    if request.headers.get("HX-Request", "").lower() == "true":
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = f"/projects/{project_id}/prompts"
        return response
    return RedirectResponse(url=f"/projects/{project_id}/prompts", status_code=303)


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/skip", response_class=HTMLResponse
)
async def skip_scene(request: Request, project_id: str, scene_id: str) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    try:
        scene_list = _scene_service(settings).skip_scene(project_id, scene_id)
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_list.html",
            context=_context(
                project=project,
                scene_list=_scene_service(settings).get_scenes(project_id),
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )
    return templates.TemplateResponse(
        request=request,
        name="partials/_scene_list.html",
        context=_context(project=project, scene_list=scene_list),
    )


@router.post("/projects/{project_id}/scenes/{scene_id}", response_class=HTMLResponse)
async def update_scene(
    request: Request,
    project_id: str,
    scene_id: str,
    title: str = Form(""),
    summary: str = Form(""),
    source_excerpt: str = Form(""),
    characters: str = Form(""),
    location: str = Form(""),
    time_of_day: str = Form(""),
    mood: str = Form(""),
    main_action: str = Form(""),
    camera_shot: str = Form(""),
    camera_angle: str = Form(""),
    visual_details: str = Form(""),
    continuity_notes: str = Form(""),
) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    service = _scene_service(settings)
    try:
        scene = service.update_scene(
            project_id,
            scene_id,
            {
                "title": title.strip(),
                "summary": summary.strip(),
                "source_excerpt": source_excerpt.strip(),
                "characters": _names(characters),
                "location": location.strip(),
                "time_of_day": time_of_day.strip(),
                "mood": mood.strip(),
                "main_action": main_action.strip(),
                "camera_shot": camera_shot.strip(),
                "camera_angle": camera_angle.strip(),
                "visual_details": _lines(visual_details),
                "continuity_notes": _lines(continuity_notes),
            },
        )
    except AppError as exc:
        scene_list = service.get_scenes(project_id)
        current_scene = (
            next(
                (item for item in scene_list.scenes if item.scene_id == scene_id), None
            )
            if scene_list
            else None
        )
        return templates.TemplateResponse(
            request=request,
            name="partials/_scene_card.html",
            context={
                "project": project,
                "scene": current_scene,
                "flash_message": exc.message,
                "flash_kind": "error",
                "error_code": exc.code,
            },
            status_code=exc.http_status,
        )
    return templates.TemplateResponse(
        request=request,
        name="partials/_scene_card.html",
        context={
            "project": project,
            "scene": scene,
            "flash_message": "Scene saved.",
            "flash_kind": "success",
        },
    )
