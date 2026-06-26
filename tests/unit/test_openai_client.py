import pytest
from pydantic import BaseModel

from app.core.errors import AppError
from app.services.openai_client import OpenAIClient


class ParsedPayload(BaseModel):
    value: str


def test_openai_client_missing_key_raises_friendly_error() -> None:
    client = OpenAIClient(None)

    with pytest.raises(AppError) as caught:
        client.parse_json(
            model="gpt-5.4-mini",
            instructions="Return JSON.",
            payload={"input": "value"},
            response_model=ParsedPayload,
            failure_code="TEST_FAILED",
            failure_message="The test failed.",
        )

    assert caught.value.code == "OPENAI_API_KEY_MISSING"
    assert caught.value.http_status == 503
