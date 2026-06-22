from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.errors import AppError, app_error_handler
from app.web.routes_characters import router as characters_router
from app.web.routes_home import router as home_router
from app.web.routes_projects import router as projects_router
from app.web.routes_prompts import router as prompts_router
from app.web.routes_scenes import router as scenes_router
from app.web.routes_story import router as story_router


def create_app() -> FastAPI:
    app = FastAPI(title="local-ai-anime-storyboard-generator")
    app.add_exception_handler(AppError, app_error_handler)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(home_router)
    app.include_router(projects_router)
    app.include_router(story_router)
    app.include_router(characters_router)
    app.include_router(scenes_router)
    app.include_router(prompts_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
