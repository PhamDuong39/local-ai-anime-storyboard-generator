from app.core.errors import AppError


def test_app_error_serializes_to_standard_shape() -> None:
    error = AppError(
        code="STORY_TOO_LARGE",
        message="This story file is too large for Phase 1.",
        http_status=413,
        details={"max_bytes": 100},
    )

    assert error.http_status == 413
    assert error.to_response_model().model_dump(mode="json") == {
        "ok": False,
        "error": {
            "code": "STORY_TOO_LARGE",
            "message": "This story file is too large for Phase 1.",
            "details": {"max_bytes": 100},
        },
    }
