import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from app.core.file_io import read_json_model, write_json
from app.core.paths import project_relative_path, project_root
from app.schemas.manifest import OutputAsset, OutputManifest


class ManifestService:
    """Persist output manifests while preserving prior generation attempts."""

    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)

    def load_or_create(self, project_id: str, job_id: str) -> OutputManifest:
        manifest_file = self._manifest_path(project_id)
        now = datetime.now(timezone.utc)
        if not manifest_file.is_file():
            return OutputManifest(
                project_id=project_id,
                latest_job_id=job_id,
                created_at=now,
                updated_at=now,
                assets=[],
            )

        manifest = read_json_model(manifest_file, OutputManifest)
        return manifest.model_copy(update={"latest_job_id": job_id, "updated_at": now})

    def save(self, project_id: str, manifest: OutputManifest) -> OutputManifest:
        validated = OutputManifest.model_validate(manifest.model_dump(mode="json"))
        write_json(self._manifest_path(project_id), validated)
        return validated

    def record_asset(
        self, project_id: str, manifest: OutputManifest, asset: OutputAsset
    ) -> OutputManifest:
        now = datetime.now(timezone.utc)
        updated_assets = [
            item for item in manifest.assets if item.asset_id != asset.asset_id
        ]
        updated = manifest.model_copy(
            update={
                "latest_job_id": asset.job_id,
                "updated_at": now,
                "assets": [*updated_assets, asset],
            }
        )
        return self.save(project_id, updated)

    def next_output_filename(
        self, project_id: str, *, scene_number: int, title: str
    ) -> str:
        stem = f"{scene_number:03d}_{slugify_scene_title(title)}"
        output_dir = project_root(self.projects_root, project_id) / "outputs/images"
        candidate = f"{stem}.png"
        version = 2
        while (output_dir / candidate).exists():
            candidate = f"{stem}_v{version}.png"
            version += 1
        return candidate

    def output_relative_path(self, project_id: str, filename: str) -> str:
        return project_relative_path(
            self.projects_root, project_id, Path("outputs/images") / filename
        )

    def _manifest_path(self, project_id: str) -> Path:
        return project_root(self.projects_root, project_id) / "outputs/manifest.json"


def slugify_scene_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_value)).strip("_")
    if not slug:
        slug = "scene"
    return slug[:60].strip("_") or "scene"
