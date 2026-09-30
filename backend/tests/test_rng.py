"""Tests for the randomness that can be replayed."""

from rowen.engine.rng import Rng

ITEMS = tuple(range(20))


def test_same_seed_gives_same_order() -> None:
    assert Rng(seed=7).shuffled(ITEMS) == Rng(seed=7).shuffled(ITEMS)


def test_shuffle_keeps_every_item() -> None:
    order, _ = Rng(seed=7).shuffled(ITEMS)

    assert order != ITEMS
    assert sorted(order) == list(ITEMS)


def test_each_use_gives_new_numbers() -> None:
    rng = Rng(seed=7)
    first, next_rng = rng.shuffled(ITEMS)
    second, _ = next_rng.shuffled(ITEMS)

    assert first != second
    assert next_rng.uses == 1
    assert rng.uses == 0


def test_different_seeds_give_different_orders() -> None:
    assert Rng(seed=7).shuffled(ITEMS) != Rng(seed=8).shuffled(ITEMS)


def test_negative_seeds_are_different_seeds() -> None:
    assert Rng(seed=-7).shuffled(ITEMS) != Rng(seed=7).shuffled(ITEMS)


def test_coin_flip_gives_both_results() -> None:
    results = {Rng(seed=seed).coin_flip()[0] for seed in range(20)}

    assert results == {0, 1}


def test_coin_flip_moves_on() -> None:
    _, next_rng = Rng(seed=7).coin_flip()

    assert next_rng.uses == 1
