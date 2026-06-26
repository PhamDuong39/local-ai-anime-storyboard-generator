from datetime import datetime, timezone

from app.core.file_io import read_json
from app.services.manifest_service import ManifestService, slugify_scene_title
from app.schemas.manifest import OutputAsset, OutputAssetStatus


NOW = datetime(2026, 6, 11, 10, 15, 30, tzinfo=timezone.utc)


def test_slugify_scene_title_is_ascii_safe_and_bounded() -> None:
    slug = slugify_scene_title("Akira enters school: a warning!!! " * 4)

    assert slug.startswith("akira_enters_school_a_warning")
    assert len(slug) <= 60
    assert "/" not in slug


def test_next_output_filename_versions_existing_files(tmp_path) -> None:
    service = ManifestService(tmp_path / "projects")
    output_dir = tmp_path / "projects/demo-project/outputs/images"
    output_dir.mkdir(parents=True)
    (output_dir / "001_school_gate.png").write_bytes(b"old")

    filename = service.next_output_filename(
        "demo-project", scene_number=1, title="School gate"
    )

    assert filename == "001_school_gate_v2.png"


def test_record_asset_writes_manifest_success_entry(tmp_path) -> None:
    service = ManifestService(tmp_path / "projects")
    manifest = service.load_or_create("demo-project", "job")
    asset = OutputAsset(
        asset_id="asset_scene_001_job",
        job_id="job",
        scene_id="scene_001",
        scene_number=1,
        scene_title="School gate",
        prompt_id="scene_001",
        output_filename="001_school_gate.png",
        output_path="outputs/images/001_school_gate.png",
        width=1280,
        height=720,
        status=OutputAssetStatus.SUCCESS,
        image_model_id="sdxl-model",
        pipeline="sdxl",
        seed=1,
        output_preset_id="youtube_standard",
        created_at=NOW,
    )

    saved = service.record_asset("demo-project", manifest, asset)

    assert saved.assets[0].scene_id == "scene_001"
    assert (
        read_json(tmp_path / "projects/demo-project/outputs/manifest.json")["assets"][
            0
        ]["output_path"]
        == "outputs/images/001_school_gate.png"
    )
