from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.project import OutputPresetId
from app.services.project_service import OUTPUT_PRESETS, ProjectService


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _service(settings: Settings) -> ProjectService:
    return ProjectService(
        settings.projects_root,
        image_model_id=settings.image_model_id,
        low_vram_image_model_id=settings.low_vram_image_model_id,
        enable_ip_adapter_faceid=settings.enable_ip_adapter_faceid,
        force_low_vram_mode=settings.force_low_vram_mode,
    )


def _form_context(**values: object) -> dict[str, object]:
    return {
        "page_title": "Create Project",
        "presets": OUTPUT_PRESETS.values(),
        "default_preset": OutputPresetId.YOUTUBE_STANDARD.value,
        **values,
    }


@router.get("/projects/new", response_class=HTMLResponse)
async def new_project_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="project_new.html",
        context=_form_context(),
    )


@router.post("/projects", response_class=HTMLResponse)
async def create_project(
    request: Request,
    project_name: str = Form(""),
    output_preset: str = Form(OutputPresetId.YOUTUBE_STANDARD.value),
    description: str = Form(""),
) -> Response:
    try:
        project = _service(get_settings()).create_project(
            project_name=project_name,
            output_preset_id=output_preset,
            description=description,
        )
    except AppError as exc:
        return templates.TemplateResponse(
            request=request,
            name="project_new.html",
            context=_form_context(
                project_name=project_name,
                selected_preset=output_preset,
                description=description,
                flash_message=exc.message,
                flash_kind="error",
                error_code=exc.code,
            ),
            status_code=exc.http_status,
        )

    return RedirectResponse(
        url=f"/projects/{project.project_id}/story",
        status_code=303,
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_dashboard(request: Request, project_id: str) -> HTMLResponse:
    project = _service(get_settings()).get_project(project_id)
    return templates.TemplateResponse(
        request=request,
        name="project_dashboard.html",
        context={"page_title": project.project_name, "project": project},
    )
