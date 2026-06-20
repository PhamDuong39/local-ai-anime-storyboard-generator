import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.schemas.scene import SceneList, SceneStatus
from app.services.project_service import ProjectService
from app.services.scene_service import SceneService


def scene(scene_id: str, scene_number: int, title: str) -> dict[str, object]:
    return {
        "scene_id": scene_id,
        "scene_number": scene_number,
        "title": title,
        "source_excerpt": f"Excerpt for {title}",
        "summary": f"Summary for {title}",
        "characters": ["Akira"],
        "location": "school",
        "time_of_day": "dusk",
        "mood": "tense",
        "main_action": title,
        "camera_shot": "wide shot",
        "camera_angle": "eye level",
        "visual_details": ["rusted gate", "orange light", "empty courtyard"],
        "continuity_notes": ["same outfit"],
        "status": "draft",
    }


def make_service(tmp_path) -> tuple[SceneService, str]:
    root = tmp_path / "projects"
    project = ProjectService(
        root,
        image_model_id="sdxl-model",
        low_vram_image_model_id="sd15-model",
    ).create_project("Episode One", "youtube_standard")
    return SceneService(root), project.project_id


def make_scene_list(project_id: str) -> SceneList:
    return SceneList.model_validate(
        {
            "project_id": project_id,
            "scene_count": 3,
            "scenes": [
                scene("scene_001", 1, "First"),
                scene("scene_002", 2, "Second"),
                scene("scene_003", 3, "Third"),
            ],
        }
    )


def test_scene_schema_rejects_invalid_id_order_and_visual_detail_count() -> None:
    data = {
        "project_id": "valid-project",
        "scene_count": 1,
        "scenes": [scene("bad-id", 1, "First")],
    }
    with pytest.raises(ValidationError):
        SceneList.model_validate(data)

    data["scenes"] = [scene("scene_001", 2, "First")]
    with pytest.raises(ValidationError):
        SceneList.model_validate(data)

    too_few_details = scene("scene_001", 1, "First")
    too_few_details["visual_details"] = ["gate", "light"]
    data["scenes"] = [too_few_details]
    with pytest.raises(ValidationError):
        SceneList.model_validate(data)


def test_scene_list_can_be_saved_and_loaded(tmp_path) -> None:
    service, project_id = make_service(tmp_path)
    expected = make_scene_list(project_id)

    service.save_scenes(project_id, expected)

    assert service.get_scenes(project_id) == expected


def test_reorder_preserves_ids_and_renumbers_active_scenes(tmp_path) -> None:
    service, project_id = make_service(tmp_path)
    service.save_scenes(project_id, make_scene_list(project_id))

    result = service.reorder_scenes(project_id, ["scene_003", "scene_001", "scene_002"])

    assert [item.scene_id for item in result.scenes] == [
        "scene_003",
        "scene_001",
        "scene_002",
    ]
    assert [item.scene_number for item in result.active_scenes] == [1, 2, 3]


def test_skip_excludes_scene_from_generation_and_renumbers_active_scenes(
    tmp_path,
) -> None:
    service, project_id = make_service(tmp_path)
    original = make_scene_list(project_id)
    service.save_scenes(project_id, original)

    result = service.skip_scene(project_id, "scene_002")

    assert result.scenes[1].status is SceneStatus.SKIPPED
    assert [item.scene_id for item in result.active_scenes] == [
        "scene_001",
        "scene_003",
    ]
    assert [item.scene_number for item in result.active_scenes] == [1, 2]
    assert [item.scene_id for item in service.get_generation_scenes(project_id)] == [
        "scene_001",
        "scene_003",
    ]


def test_reorder_rejects_missing_or_duplicate_scene_ids(tmp_path) -> None:
    service, project_id = make_service(tmp_path)
    service.save_scenes(project_id, make_scene_list(project_id))

    with pytest.raises(AppError) as caught:
        service.reorder_scenes(project_id, ["scene_001", "scene_001"])

    assert caught.value.code == "SCENE_REORDER_INVALID"


def test_update_scene_validates_fields_and_changes_status(tmp_path) -> None:
    service, project_id = make_service(tmp_path)
    service.save_scenes(project_id, make_scene_list(project_id))

    updated = service.update_scene(
        project_id,
        "scene_001",
        {"title": "Changed title", "summary": "Changed summary"},
    )

    assert updated.title == "Changed title"
    assert updated.status is SceneStatus.NEEDS_EDIT

    with pytest.raises(AppError) as caught:
        service.update_scene(project_id, "scene_001", {"summary": ""})
    assert caught.value.code == "SCENE_UPDATE_INVALID"


def test_cannot_skip_last_active_scene(tmp_path) -> None:
    service, project_id = make_service(tmp_path)
    service.save_scenes(project_id, make_scene_list(project_id))
    service.skip_scene(project_id, "scene_001")
    service.skip_scene(project_id, "scene_002")

    with pytest.raises(AppError) as caught:
        service.skip_scene(project_id, "scene_003")

    assert caught.value.code == "SCENE_SKIP_INVALID"
