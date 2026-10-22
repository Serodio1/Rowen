"""Tests for the API's OpenAPI document in ``backend/openapi.json``."""

import json
from pathlib import Path

import pytest

from rowen.api import openapi
from rowen.api.app import app

# backend/openapi.json, found from this file: backend/tests/test_api_openapi.py.
OPENAPI_JSON = Path(__file__).parents[1] / "openapi.json"


def test_openapi_json_is_the_document_of_the_api() -> None:
    # The frontend's types are generated from this file, so it must describe
    # the API as it is now.
    assert OPENAPI_JSON.read_text(encoding="utf-8") == openapi.document(), (
        "backend/openapi.json is out of date with the API. In backend, run: "
        "uv run python -m rowen.api.openapi"
    )


def test_the_document_is_the_one_fastapi_makes() -> None:
    assert json.loads(openapi.document()) == app.openapi()


def test_endpoints_are_named_after_their_functions() -> None:
    operations = {
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    }

    assert operations == {
        "list_decks",
        "create_match",
        "get_match",
        "play",
        "list_matches",
        "get_stats",
        "register",
        "log_in",
        "get_session",
        "log_out",
    }


def test_main_writes_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = tmp_path / "openapi.json"
    monkeypatch.setattr(openapi, "OPENAPI_JSON", written)

    openapi.main()

    # Read as bytes: "\n" line endings on every system.
    assert written.read_bytes() == openapi.document().encode()


def test_main_writes_next_to_the_backend_project() -> None:
    assert openapi.OPENAPI_JSON == OPENAPI_JSON
