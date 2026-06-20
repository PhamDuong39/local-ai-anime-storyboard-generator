from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.character import CharacterMetadata
from app.services.character_service import CharacterService, CharacterUpload
from app.services.project_service import ProjectService


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

WARNING_MESSAGES = {
    "LOW_RESOLUTION": (
        "This image is smaller than recommended and may reduce consistency quality."
    ),
    "NON_PREFERRED_FORMAT": "PNG is recommended, but this image is usable.",
    "FILENAME_MISMATCH_POSSIBLE": (
        "This filename may be hard to match to a story character. "
        "A simple name such as Akira.png works best."
    ),
}


def _project_service(settings: Settings) -> ProjectService:
    return ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
        enable_ip_adapter_faceid=settings.enable_ip_adapter_faceid,
        force_low_vram_mode=settings.force_low_vram_mode,
    )


def _character_service(settings: Settings) -> CharacterService:
    return CharacterService(settings.projects_root)


def _page_context(
    *,
    project: object,
    metadata: CharacterMetadata | None = None,
    **values: object,
) -> dict[str, object]:
    return {
        "page_title": "Upload Characters",
        "project": project,
        "characters": metadata.characters if metadata else [],
        "warning_messages": WARNING_MESSAGES,
        **values,
    }


@router.get("/projects/{project_id}/characters", response_class=HTMLResponse)
async def characters_page(request: Request, project_id: str) -> HTMLResponse:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    metadata = _character_service(settings).get_characters(project_id)
    return templates.TemplateResponse(
        request=request,
        name="character_upload.html",
        context=_page_context(project=project, metadata=metadata),
    )


@router.post("/projects/{project_id}/characters", response_class=HTMLResponse)
async def upload_characters(
    request: Request,
    project_id: str,
    character_files: list[UploadFile] | None = File(default=None),
) -> Response:
    settings = get_settings()
    project = _project_service(settings).get_project(project_id)
    service = _character_service(settings)
    previous_metadata = service.get_characters(project_id)
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"

    uploads: list[CharacterUpload] = []
    for upload_file in character_files or []:
        try:
            uploads.append(
                CharacterUpload(
                    filename=upload_file.filename,
                    content=await upload_file.read(),
                )
            )
        finally:
            await upload_file.close()

    try:
        metadata = service.save_characters(project_id, uploads)
    except AppError as exc:
        context = _page_context(
            project=project,
            metadata=previous_metadata,
            flash_message=exc.message,
            flash_kind="error",
            error_code=exc.code,
        )
        return templates.TemplateResponse(
            request=request,
            name=(
                "partials/_character_validation.html"
                if is_htmx
                else "character_upload.html"
            ),
            context=context,
            status_code=exc.http_status,
        )

    if is_htmx:
        return templates.TemplateResponse(
            request=request,
            name="partials/_character_validation.html",
            context=_page_context(
                project=project,
                metadata=metadata,
                flash_message="Character images uploaded and validated successfully.",
                flash_kind="success",
            ),
        )

    return RedirectResponse(
        url=f"/projects/{project_id}/scenes",
        status_code=303,
    )
