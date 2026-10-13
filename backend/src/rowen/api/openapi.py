"""Write the web API's OpenAPI document to ``backend/openapi.json``.

The OpenAPI document describes every endpoint and every JSON shape of the API.
The frontend generates its TypeScript types from this file, so the browser's
code and the API agree on every field (ADR 0008).

After changing the API, write the file again, in ``backend``:
``uv run python -m rowen.api.openapi``. A test fails while the file is out of
date with the API.
"""

import json
from pathlib import Path

from rowen.api.app import app

# backend/openapi.json: this file is backend/src/rowen/api/openapi.py.
OPENAPI_JSON = Path(__file__).parents[3] / "openapi.json"


def document() -> str:
    """Return the API's OpenAPI document, as the text of ``openapi.json``."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    """Write the API's OpenAPI document to ``backend/openapi.json``."""
    # Always "\n", also on Windows, as .gitattributes asks for every text file.
    OPENAPI_JSON.write_text(document(), encoding="utf-8", newline="\n")


# Only when run with "python -m"; the tests call main() instead.
if __name__ == "__main__":  # pragma: no cover
    main()
