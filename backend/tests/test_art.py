"""Tests that every card and leader has its art in the frontend, and only
they do.

The page shows a card's art from ``frontend/src/art/<id>.webp`` (made by
``scripts/convert_art.py``), and a placeholder when there is none. The card
ids are in the data files, so this check lives with them.
"""

from pathlib import Path

from rowen.data import deck_ids, load_deck

ART = Path(__file__).resolve().parents[2] / "frontend" / "src" / "art"


def card_ids() -> set[str]:
    """Return the id of every card in every deck, special cards included, and
    of every deck's leader.
    """
    decks = [load_deck(deck_id) for deck_id in deck_ids()]
    cards = {card.id for deck in decks for card in deck.cards}
    return cards | {deck.leader.id for deck in decks if deck.leader is not None}


def test_every_card_has_its_art() -> None:
    missing = {id for id in card_ids() if not (ART / f"{id}.webp").is_file()}

    assert missing == set()


def test_every_picture_is_a_cards_art_in_webp() -> None:
    pictures = list(ART.iterdir())

    # A misspelt name would leave its card with a placeholder.
    assert {picture.name for picture in pictures} == {f"{id}.webp" for id in card_ids()}
    for picture in pictures:
        header = picture.read_bytes()[:12]
        assert header[:4] == b"RIFF", picture.name
        assert header[8:] == b"WEBP", picture.name
