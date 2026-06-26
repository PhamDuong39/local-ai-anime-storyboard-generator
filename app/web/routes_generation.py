from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.schemas.jobs import GenerationJob, GenerationJobStatus
from app.services.generation_job_service import GenerationJobService
from app.services.generation_service import GenerationService


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

POLLING_STATUSES = {
    GenerationJobStatus.QUEUED,
    GenerationJobStatus.RUNNING,
    GenerationJobStatus.CANCEL_REQUESTED,
}


def _generation_job_service(settings: Settings) -> GenerationJobService:
    return GenerationJobService(settings.projects_root)


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "")


def _status_payload(project_id: str, job: GenerationJob | None) -> dict[str, object]:
    return {
        "ok": True,
        "project_id": project_id,
        "data": None if job is None else job.model_dump(mode="json"),
    }


def _context(
    settings: Settings,
    project_id: str,
    *,
    confirm_cpu_slow: bool = False,
    **values: object,
) -> dict[str, object]:
    job_service = _generation_job_service(settings)
    readiness = job_service.check_readiness(
        project_id, confirm_cpu_slow=confirm_cpu_slow
    )
    job = job_service.get_status(project_id)
    return {
        "page_title": "Generate Storyboard Images",
        "project_id": project_id,
        "readiness": readiness,
        "job": job,
        "polling_statuses": {status.value for status in POLLING_STATUSES},
        **values,
    }


@router.get("/projects/{project_id}/generation", response_class=HTMLResponse)
async def generation_page(request: Request, project_id: str) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="generation_progress.html",
        context=_context(settings, project_id),
    )


@router.post("/projects/{project_id}/generation/start")
async def start_generation(
    request: Request,
    project_id: str,
    confirm_cpu_slow: bool = Form(False),
) -> Response:
    settings = get_settings()
    job = _generation_job_service(settings).start_job(
        project_id,
        confirm_cpu_slow=confirm_cpu_slow,
    )
    GenerationService(settings.projects_root).generate_mock_images(
        project_id, job.job_id
    )
    completed_job = GenerationJobService(settings.projects_root).get_status(project_id)
    response_job = completed_job or job
    if _wants_json(request) and not _is_htmx(request):
        return JSONResponse(
            {
                "ok": True,
                "project_id": project_id,
                "next_url": f"/projects/{project_id}/generation",
                "data": {"job": response_job.model_dump(mode="json")},
            }
        )
    if _is_htmx(request):
        return templates.TemplateResponse(
            request=request,
            name="partials/_generation_status.html",
            context={
                **_context(settings, project_id),
                "job": response_job,
                "flash_message": "Mock generation completed.",
                "flash_kind": "success",
            },
        )
    return RedirectResponse(url=f"/projects/{project_id}/generation", status_code=303)


@router.get("/projects/{project_id}/generation/status")
async def generation_status(request: Request, project_id: str) -> Response:
    settings = get_settings()
    job = _generation_job_service(settings).get_status(project_id)
    if _wants_json(request) and not _is_htmx(request):
        return JSONResponse(_status_payload(project_id, job))
    return (
        JSONResponse(_status_payload(project_id, job))
        if not _is_htmx(request)
        else templates.TemplateResponse(
            request=request,
            name="partials/_generation_status.html",
            context={**_context(settings, project_id), "job": job},
        )
    )
