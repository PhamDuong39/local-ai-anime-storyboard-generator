import json
from typing import Any, TypeVar

from pydantic import BaseModel, SecretStr, ValidationError

from app.core.errors import AppError


ParsedModel = TypeVar("ParsedModel", bound=BaseModel)


class OpenAIClient:
    """Small OpenAI SDK wrapper that keeps secrets and raw payloads out of logs."""

    def __init__(self, api_key: SecretStr | str | None) -> None:
        if isinstance(api_key, SecretStr):
            api_key = api_key.get_secret_value()
        self.api_key = api_key.strip() if api_key else None

    def parse_json(
        self,
        *,
        model: str,
        instructions: str,
        payload: dict[str, Any],
        response_model: type[ParsedModel],
        failure_code: str,
        failure_message: str,
        invalid_response_code: str | None = None,
        invalid_response_message: str | None = None,
    ) -> ParsedModel:
        if not self.api_key:
            raise AppError(
                code="OPENAI_API_KEY_MISSING",
                message=(
                    "OpenAI API key is not configured. Add OPENAI_API_KEY to .env "
                    "or enable mock mode for offline testing."
                ),
                http_status=503,
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            response = client.responses.parse(
                model=model,
                instructions=instructions,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=response_model,
                store=False,
                truncation="disabled",
            )
        except AppError:
            raise
        except ValidationError as exc:
            raise AppError(
                code=invalid_response_code or failure_code,
                message=invalid_response_message or failure_message,
                http_status=502,
            ) from exc
        except Exception as exc:
            raise AppError(
                code=failure_code,
                message=failure_message,
                http_status=502,
            ) from exc

        parsed = getattr(response, "output_parsed", None)
        if isinstance(parsed, response_model):
            return parsed

        raise AppError(
            code=invalid_response_code or failure_code,
            message=invalid_response_message or failure_message,
            http_status=502,
        )
