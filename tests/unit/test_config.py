from pathlib import Path

from app.core.config import Settings


def test_settings_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)

    assert settings.openai_api_key is None
    assert settings.openai_scene_model == "gpt-5.4-mini"
    assert settings.openai_prompt_model == "gpt-5.4-mini"
    assert settings.projects_root == Path("projects")
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8000
    assert settings.default_output_preset == "youtube_standard"
    assert settings.enable_ip_adapter_faceid == "auto"
    assert settings.force_low_vram_mode is False
    assert settings.has_openai_api_key is False


def test_settings_environment_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_PORT", "9001")
    monkeypatch.setenv("PROJECTS_ROOT", "custom-projects")
    monkeypatch.setenv("OPENAI_API_KEY", "not-logged-secret")
    monkeypatch.setenv("FORCE_LOW_VRAM_MODE", "true")
    monkeypatch.setenv("ENABLE_IP_ADAPTER_FACEID", "force")

    settings = Settings(_env_file=None)

    assert settings.app_port == 9001
    assert settings.projects_root == Path("custom-projects")
    assert settings.force_low_vram_mode is True
    assert settings.enable_ip_adapter_faceid == "force"
    assert settings.has_openai_api_key is True
    assert "not-logged-secret" not in repr(settings)


def test_settings_load_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("APP_PORT=8123\nLOG_LEVEL=DEBUG\n", encoding="utf-8")

    settings = Settings()

    assert settings.app_port == 8123
    assert settings.log_level == "DEBUG"
