"""Letting the AI play through the API, as the page does after each move."""

import httpx2
from fastapi.testclient import TestClient

# The AI is always player 1 (rowen.api.app).
AI = 1


def let_ai_play(client: TestClient, response: httpx2.Response) -> httpx2.Response:
    """Let the AI play if the match in ``response`` is at its turn: its answer.

    That is what the page does with each match it gets. Otherwise, or if
    ``response`` is an error, return ``response``.
    """
    if response.status_code not in {200, 201}:
        return response
    match = response.json()
    if match["view"]["current"] != AI or match["view"]["match_over"]:
        return response
    return client.post(
        f"/matches/{match['id']}/ai-turn", json={"version": match["version"]}
    )
