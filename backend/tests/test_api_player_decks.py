"""Tests for the stores of the decks players build: the same for both stores.

Each test runs once with the store in memory and once with the one in
PostgreSQL (``any_decks``, in tests/conftest.py), which is skipped without a
test database.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from rowen.api.accounts import AccountStore
from rowen.api.player_decks import MAX_DECKS, DeckStore

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
COPIES = {"human": 5, "soldier": 3}

type Stores = tuple[DeckStore, AccountStore]


def owner(accounts: AccountStore, username: str = "rui") -> UUID:
    """Make an account and return its id: a deck needs an owner."""
    account = accounts.create_account(username, "a hash")
    assert account is not None
    return account.id


def test_a_deck_is_kept_as_it_was_built(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)

    deck = decks.create_deck(rui, "Mine", "humans", COPIES, NOW)

    assert deck is not None
    assert (deck.owner, deck.name, deck.faction) == (rui, "Mine", "humans")
    assert deck.copies == COPIES
    assert deck.created_at == NOW
    assert decks.get_deck(rui, deck.id) == deck
    assert decks.list_decks(rui) == (deck,)


def test_an_owners_decks_come_oldest_first(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    later = decks.create_deck(rui, "Later", "humans", COPIES, NOW + timedelta(1))
    first = decks.create_deck(rui, "First", "robots", COPIES, NOW)

    assert decks.list_decks(rui) == (first, later)


def test_decks_made_at_the_same_time_come_in_the_order_of_their_ids(
    any_decks: Stores,
) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    made = [decks.create_deck(rui, str(n), "humans", COPIES, NOW) for n in range(3)]

    listed = decks.list_decks(rui)

    assert [deck.id for deck in listed] == sorted(deck.id for deck in made if deck)


def test_a_player_sees_only_their_own_decks(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui, ana = owner(accounts, "rui"), owner(accounts, "ana")
    deck = decks.create_deck(rui, "Mine", "humans", COPIES, NOW)
    assert deck is not None

    assert decks.list_decks(ana) == ()
    assert decks.get_deck(ana, deck.id) is None
    assert decks.replace_deck(ana, deck.id, "Hers", "robots", {}) is None
    assert not decks.delete_deck(ana, deck.id)
    # Rui's deck is as it was.
    assert decks.get_deck(rui, deck.id) == deck


def test_a_deck_that_doesnt_exist_is_none(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)

    assert decks.get_deck(rui, uuid4()) is None
    assert decks.replace_deck(rui, uuid4(), "Mine", "humans", COPIES) is None
    assert not decks.delete_deck(rui, uuid4())


def test_a_deck_can_be_changed_all_at_once(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    deck = decks.create_deck(rui, "Mine", "humans", COPIES, NOW)
    assert deck is not None

    changed = decks.replace_deck(rui, deck.id, "Robots", "robots", {"robot": 2})

    assert changed is not None
    assert (changed.id, changed.owner, changed.created_at) == (deck.id, rui, NOW)
    assert (changed.name, changed.faction) == ("Robots", "robots")
    assert changed.copies == {"robot": 2}
    assert decks.get_deck(rui, deck.id) == changed


def test_a_deleted_deck_is_gone(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    deck = decks.create_deck(rui, "Mine", "humans", COPIES, NOW)
    assert deck is not None

    assert decks.delete_deck(rui, deck.id)

    assert decks.get_deck(rui, deck.id) is None
    assert decks.list_decks(rui) == ()
    assert not decks.delete_deck(rui, deck.id)


def test_a_player_may_keep_up_to_ten_decks(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui, ana = owner(accounts, "rui"), owner(accounts, "ana")
    for n in range(MAX_DECKS):
        assert decks.create_deck(rui, str(n), "humans", COPIES, NOW) is not None

    assert decks.create_deck(rui, "One more", "humans", COPIES, NOW) is None
    assert len(decks.list_decks(rui)) == MAX_DECKS
    # Another player's decks don't count.
    assert decks.create_deck(ana, "Hers", "humans", COPIES, NOW) is not None


def test_deleting_a_deck_makes_room_for_another(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    made = [
        decks.create_deck(rui, str(n), "humans", COPIES, NOW) for n in range(MAX_DECKS)
    ]
    assert made[0] is not None

    decks.delete_deck(rui, made[0].id)

    assert decks.create_deck(rui, "New", "humans", COPIES, NOW) is not None


def test_changing_the_copies_given_doesnt_change_the_deck(any_decks: Stores) -> None:
    decks, accounts = any_decks
    rui = owner(accounts)
    copies = dict(COPIES)
    deck = decks.create_deck(rui, "Mine", "humans", copies, NOW)
    assert deck is not None

    copies["human"] = 1

    kept = decks.get_deck(rui, deck.id)
    assert kept is not None
    assert kept.copies == COPIES
