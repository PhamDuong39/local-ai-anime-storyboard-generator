from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.project_service import ProjectService
from app.services.story_service import MAX_STORY_FILE_BYTES, StoryService, StoredStory


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


def _story_service(settings: Settings) -> StoryService:
    return StoryService(settings.projects_root)


def _page_context(
    *,
    project: object,
    stored_story: StoredStory | None = None,
    **values: object,
) -> dict[str, object]:
    return {
        "page_title": "Upload Story",
        "project": project,
        "story": stored_story.metadata if stored_story else None,
        "story_preview": stored_story.preview if stored_story else None,
        **values,
    }


@router.get("/projects/{project_id}/story", response_class=HTMLResponse)
async def story_page(request: Request, project_id: str) -> HTMLResponse:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    stored_story = _story_service(settings).get_story(project_id)
    return templates.TemplateResponse(
        request=request,
        name="story_upload.html",
        context=_page_context(project=project, stored_story=stored_story),
    )


@router.post("/projects/{project_id}/story", response_class=HTMLResponse)
async def upload_story(
    request: Request,
    project_id: str,
    story_file: UploadFile | None = File(default=None),
) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    service = _story_service(settings)
    previous_story = service.get_story(project_id)
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"

    filename: str | None = None
    content: bytes | None = None
    if story_file is not None:
        filename = story_file.filename
        content = await story_file.read(MAX_STORY_FILE_BYTES + 1)
        await story_file.close()

    try:
        service.save_story(project_id, filename, content)
        stored_story = service.get_story(project_id)
    except AppError as exc:
        context = _page_context(
            project=project,
            stored_story=previous_story,
            flash_message=exc.message,
            flash_kind="error",
            error_code=exc.code,
        )
        return templates.TemplateResponse(
            request=request,
            name=(
                "partials/_story_validation.html" if is_htmx else "story_upload.html"
            ),
            context=context,
            status_code=exc.http_status,
        )

    if is_htmx:
        return templates.TemplateResponse(
            request=request,
            name="partials/_story_validation.html",
            context=_page_context(
                project=project,
                stored_story=stored_story,
                flash_message="Story uploaded and validated successfully.",
                flash_kind="success",
            ),
        )

    return RedirectResponse(
        url=f"/projects/{project_id}/characters",
        status_code=303,
    )
